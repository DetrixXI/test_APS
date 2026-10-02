from sqlalchemy import insert, select, delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError, InterfaceError
from elasticsearch import AsyncElasticsearch, helpers
from elasticsearch.exceptions import TransportError, ConnectionError, NotFoundError
from datetime import datetime
from fastapi import HTTPException
from pathlib import Path
from typing import Generator
import csv, ast, logging, asyncio

from db.models import Posts, Rubrics, posts_rubrics_relation as prr
from es.es_worker import ES_worker
from settings import Settings
from es.es_start import es_helper

DEL_TABLE = str.maketrans('','',"[]',]")
DB_PATH = Path(Settings.DB_SQL_URL)
logger = logging.getLogger(__name__)


class Doc_Delete():
    def __init__(self, ses: AsyncSession, es_client: AsyncElasticsearch):
        self.ses: AsyncSession = ses
        self.es_client: AsyncElasticsearch = ES_worker(es_client)

    async def __del_from_es(self, post_id: int):
        try:
            await self.es_client.delete_from_index_by_id(post_id)
        except NotFoundError:
            # т.к. в индексе уже нет документа - можно пропустить ошибку 
            # вдруг в прошлый раз бд упала после корректной отработки es
            pass

    async def __del_from_bd(self, post_id):
        # запоминаем рубрики, которые нужно потом проверить - вдруг после удаления поста на них уже никто не ссылается
        affected_rubr = await self.ses.execute(select(prr.c.rubric_id).where(prr.c.post_id == post_id))
        affected_rubr_ids = [r[0] for r in affected_rubr]
        await self.ses.execute(delete(Posts).where(Posts.id == post_id))

        # вытаскиваем все rubric_id, который были затронуты при удалении
        # из prr - если ничего не вытащилось - на все затронутые рубрики больше никто не ссылается,
        # иначе удаляем разность между затронутыми и еще связанными рубриками
        still_linked = await self.ses.execute(
            select(prr.c.rubric_id)
            .where(prr.c.rubric_id.in_(affected_rubr_ids))
            .group_by(prr.c.rubric_id)
        )
        still_linked_ids = [r[0] for r in still_linked]


        orphan_rubr_ids =  set(affected_rubr_ids).difference(still_linked_ids)

        if orphan_rubr_ids:
            await self.ses.execute(delete(Rubrics).where(Rubrics.id.in_(orphan_rubr_ids)))
        await self.ses.commit()
     
    async def delete_document_by_id(self, post_id:int):
        post = await self.ses.execute(select(Posts.id).where(Posts.id == post_id))
        if not post.scalar():
            raise HTTPException(404, f"Пост с id {post_id} не найден")
        # специально последовательно удаляем из ES и потом из БД
        # т.к. если сделать иначе - упадет es, а бд нет и клиент не повторит запрос
        # то в es останется запись, а в бд - нет, в итоге при обращении к посту, который
        # остался в es вылетит ошибка из за пустой бд
        try:
            await self.__del_from_es(post_id)
        except (TransportError, ConnectionError) as tce:
            logger.error(f"ES: не удалось удалить {post_id}: {tce}")
            raise HTTPException(
            status_code=503,
            detail=f"Поисковый индекс недоступен, повторите запрос")

        
        try:
            await self.__del_from_bd(post_id)

        # OperationalError - бд доступна, но по какой-то причине не может выполнить запрос сейчас же (перезапуск или пул исчерпался)
        # InterfaceError - ошибка со стороны драйвера бд (разорвано соединение в процессе транзакции)
        # TE - бд залочилась из за жругой транзакции
        except (OperationalError, InterfaceError, TimeoutError) as e:
            await self.ses.rollback()
            logger.error(f"БД: временная ошибка удаления {post_id}: {e}")
            raise HTTPException(503, 'БД временно недоступна, повторите запрос')
        except Exception as e:
            await self.ses.rollback()
            logger.error(f"БД: ошибка: {e}", exc_info=True)
            raise HTTPException(500, 'Внутренняя ошибка БД')
        else:
            return {'Success': True}
        ...
        
class Doc_Search():
    def __init__(self, ses: AsyncSession, es_client: AsyncElasticsearch):
        self.ses: AsyncSession = ses
        self.es_client: AsyncElasticsearch = ES_worker(es_client)

    async def __search_id_in_elastic(self, query: str) ->list[int]:
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                hits = (await self.es_client.search_by_query(query))['hits']['hits']
                return [int(hit['_id']) for hit in hits]
            except (TransportError, ConnectionError) as tce:
                if attempt == max_attempts - 1:
                    status = 504 if isinstance(tce, TransportError) else 503
                    raise HTTPException(status, str(tce))
                delay = 0.5 * (2**attempt)
                logger.warning(f"Попытка №{attempt} - {tce}")
                await asyncio.sleep(delay)

    async def __search_data_in_bd(self, posts_ids: list[int]):
        stm = (select(Posts.id, Posts.created_date, Rubrics.rubric_code, Posts.text)
               .join(prr, Posts.id == prr.c.post_id)
               .join(Rubrics, Rubrics.id == prr.c.rubric_id)
               .where(Posts.id.in_(posts_ids))
               .order_by(Posts.created_date))
        
        res = await self.ses.execute(stm)
        return res.all()
        
    async def search_document_by_query(self, query: str) -> list[dict]:
        relevant_post_ids = await self.__search_id_in_elastic(query)
        if not relevant_post_ids:
            return []
        
        posts_data = await self.__search_data_in_bd(relevant_post_ids)

        posts_dict = dict()
        for row in posts_data:
            pid = row.id
            if row.id not in posts_dict:
                posts_dict[pid] = {
                    'post_id': pid,
                    'created_date': row.created_date,
                    'rubric_codes': [],
                    'text': row.text
                }
            posts_dict[pid]['rubric_codes'].append(row.rubric_code)
        return posts_dict

class CSV_Parse_Service():
    def __init__(self, ses: AsyncSession, es_client: AsyncElasticsearch):
        self.ses: AsyncSession = ses
        self.es_client: AsyncElasticsearch = es_client
        self._es_sem = asyncio.Semaphore(5)

    @staticmethod
    def parse_csv(csv_adress: str, encoding = 'utf-8') ->Generator[list, None, None]:
        '''возвращает batch из [ str, datetime, list[str] ]'''
        with open(csv_adress, 'r', encoding=encoding, newline='') as f:
            reader = csv.reader(f)
            next(reader, None)

            batch = []
            line_num_errors = []
            for line_num, row in enumerate(reader, start=1):
                errors = []
                text = row[0]
                # пробуем взять дату
                try:
                    date = datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S")
                except ValueError as e:
                    errors.append(f'Невалидная дата! Ошибка: {e}')

                # пробуем взять рубрики
                try:
                    vk_ids = ast.literal_eval(row[2])
                    if not isinstance(vk_ids, list):
                        raise ValueError('не список')
                except ValueError:
                    errors.append(f'Некорректный формат записи id рубрик!')

                #если есть ошибки - скип
                if errors:
                    logger.error(f'Строка {line_num} пропущена т.к.: {"; ".join(errors)}')
                    line_num_errors.append(line_num)
                    continue

                batch.append([text, date, vk_ids])

                if len(batch) == 500:
                    yield batch
                    batch = []
            if batch:
                yield batch

    async def __fill_bd(self, batch: list) -> dict:
        """вставка в бд, потом возвращаем данные для эластика"""
        # ПОСТЫ
        posts_data = [
            {"text": line[0], "created_date": line[1]} for line in batch]
        res = await self.ses.execute(
            insert(Posts).values(posts_data).returning(Posts.id, Posts.text))
        posts_data = res.mappings().all() # list словарей с ключами id и text


        # РУБРИКИ
        all_rubrics_data =  {
            vk_code for line in batch for vk_code in line[2]}
        await self.ses.execute(sqlite_insert(Rubrics)
                               .values([{'rubric_code': code} for code in all_rubrics_data])
                               .on_conflict_do_nothing(index_elements=['rubric_code']))
        # из-за .on_conflict_do_nothing не используем returning на insert т.к. вернутся id только для вставленных рубрик
        # старые проигнорируются, потому придется сделать отдельный select все равно
        res = await self.ses.execute(
            select(Rubrics.rubric_code, Rubrics.id)
            .where(Rubrics.rubric_code.in_(all_rubrics_data)))
        rubric_code_to_id = {r.rubric_code: r.id for r in res.mappings()}

        # т.к. при insert сохраняется порядок, posts_data имеет тот же порядок, что и batch
        # тогда мы можем корректно поставить в соответствие коды рубрик (они лежат в batch) и посты
        rel = [
            {"post_id": post['id'], 'rubric_id': rubric_code_to_id[code]}
            for post, doc in zip(posts_data, batch)
            for code in doc[2] 
        ]
        await self.ses.execute(insert(prr).values(rel))

        return {el['id']: el['text'] for el in posts_data}

    async def __fill_index(self, posts: dict, ind: int):
        """posts = {post.id: post.text}"""
        async with self._es_sem:
            tasks = [{"_index": es_helper.index_name,
                        "_source": {'text': text},
                        "_id": str(id)}
                    for id, text in posts.items()]

            success, errors = await helpers.async_bulk(
            client=self.es_client,
            actions=tasks,
            chunk_size=500,
            max_retries=3,
            raise_on_error=False
            )
            if errors:
                for err in errors:
                    logger.error(f'БАТЧ {ind} - Ошибка: {err}')
                logger.error(f'Ошибки в {len(errors)} БАТЧАХ из {len(errors)+success}')
            else:
                logger.info(f'Вставка прошла успешно')
    ...

    async def fill_bd_by_csv(self, csv_adress = 'posts.csv'):
        not_loaded_batch = []
        es_tasks = []
        
        parse_csv_gen = self.parse_csv(csv_adress)
        for ind, batch in enumerate(parse_csv_gen):
            try:
                data_for_es = await self.__fill_bd(batch)
                await self.ses.commit()
                es_tasks.append(asyncio.create_task(self.__fill_index(data_for_es, ind)))
            except Exception as e:
                await self.ses.rollback()
                logger.error(f'Батч {ind} - ошибка {e}')
                not_loaded_batch.append(str(ind))
        else:
            if not_loaded_batch:
                logger.error(f'Из {ind} батчей ошибок - {len(not_loaded_batch)}.\nОшибки в №{", ".join(not_loaded_batch)}')
            logger.info(f'Все ок!')

        # надо подождать, если какие то загрузки в индекс еще не завершились
        await asyncio.gather(*es_tasks)

