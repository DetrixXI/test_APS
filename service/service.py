from sqlalchemy.ext.asyncio import AsyncSession
from elasticsearch import AsyncElasticsearch
from datetime import datetime
import csv
from pathlib import Path

from models.models import Posts, Rubrics
from dto.dto import new_document, correct_document, post_from_db, response_document, New_post_dto, New_rubric_dto
from db.repo_workers import Rubric_worker, Post_worker, Prr_worker
from es.es_worker import ES_worker
from settings import Settings

DEL_TABLE = str.maketrans('','',"[]',]")
DB_PATH = Path(Settings.DB_SQL_URL)

class DocumentService():
    def __init__(self, ses: AsyncSession, es_client: AsyncElasticsearch):
        self.ses: AsyncSession = ses
        self.es_client: AsyncElasticsearch = es_client

    @staticmethod
    async def __create_correct_document(document: list[str]) -> correct_document:
        suit_date = datetime.strptime(document[1], "%Y-%m-%d %H:%M:%S") if not isinstance(document[1], datetime) else document[1]
        suit_rubrics = document[2].translate(DEL_TABLE).split(' ') if not isinstance(document[2], list) else document[2]
        text = document[0]
        return correct_document(text=text, created_date=suit_date, rubric_codes=suit_rubrics)

    async def __create_post_rubric_response(self, post_id: int) -> response_document:
        prr_worker = Prr_worker(self.ses)
        post_worker = Post_worker(self.ses)
        rubric_worker = Rubric_worker(self.ses)

        post = await post_worker.select_post(post_id)

        rubrics_ids = await prr_worker.select_rels_by_pid(post_id)

        rubrics = []
        for rid in rubrics_ids:
            rubrics.append((await rubric_worker.select_rubric(rid)).rubric_code)

        return response_document(text=post.text, created_date=post.created_date, rubric_codes=rubrics, id=post.id)
        ...
    
    async def bulk_insertion_documents(self, adress_csv: str):
        data_for_es = {}
        post_worker = Post_worker(self.ses)
        if DB_PATH.is_file():
            if (raw_data := await post_worker.select_all_posts()) == []:
                with open(adress_csv, 'r', encoding='utf-8') as f:
                        data = csv.reader(f, delimiter=',')
                        next(data)
            
                        rubric_worker = Rubric_worker(self.ses)
                        prr_worker = Prr_worker(self.ses)
            
                        posts_and_idx = {}
                        rubrics_and_idx = {}
                        pr_relation = {}
                        pr_rel_to_db = []
            
            
                        posts_data = []
                        rubrics_data = []
            
                        for id, document in enumerate(data):
                            document = await self.__create_correct_document(document)
                            # для постов
                            post_h = document.text[:15]+document.created_date.strftime("%Y:%m:%d:%H:%M:%S")
                            posts_data.append({'text': document.text, 'created_date': document.created_date})
                            posts_and_idx.update({post_h: 1})
                            # для рубрик
                            for rubric in document.rubric_codes:
                                if rubric not in rubrics_and_idx:
                                    rubrics_data.append({'rubric_code': rubric})
                                    rubrics_and_idx.update({rubric: 1})
                                #для релейшенов
                                pr_relation[post_h] = pr_relation.get(post_h, []) + [rubric]   
                        posts: list[Posts] = await post_worker.insert_post(posts_data)
                        rubrics: list[Rubrics] = await rubric_worker.insert_rubric(rubrics_data)
                        for rubric in rubrics:
                            rubrics_and_idx[rubric.rubric_code] = rubric.id
                        for raw_post in posts:
                            post_h = raw_post.text[:15]+raw_post.created_date.strftime("%Y:%m:%d:%H:%M:%S")
                            data_for_es.update({raw_post.id: raw_post.text})
                            for rubric in pr_relation[post_h]:
                                pr_rel_to_db.append({'post_id': raw_post.id, "rubric_id": rubrics_and_idx[rubric]})
            
                        await prr_worker.insert_prr_relation(pr_rel_to_db)
                        await self.ses.commit()
            else:
                data_for_es = {el.id: el.text for el in raw_data}
        else:
            raise FileNotFoundError('Нет файла БД')

        es_worker = ES_worker(self.es_client)
        await es_worker.bulk_insert_to_index(data_for_es)
        return True

    async def insert_document(self, new_doc: new_document):
        es_worker = ES_worker(self.es_client)
        post_worker = Post_worker(self.ses)
        rubric_worker = Rubric_worker(self.ses)
        prr_woker = Prr_worker(self.ses)

        new_doc = list(new_doc.model_dump().values())
        document = await self.__create_correct_document(new_doc)
        rubrics = [Rubrics(rubric_code = el) for el in document.rubric_codes]

        post = await post_worker.insert_post(New_post_dto(text=document.text, created_date=document.created_date))
        await self.ses.commit()

        pr_relation = []
        for rubric_code in document.rubric_codes:
            rubric = await rubric_worker.insert_rubric(New_rubric_dto(rubric_code=rubric_code))
            pr_relation.append({'post_id': post.id, "rubric_id": rubric.id})

        await prr_woker.insert_prr_relation(pr_relation)

        await es_worker.insert_to_index(post_from_db(text=post.text, id=post.id))
        return {'Success': True}
        
    async def delete_document_by_pid(self, id: int):
        post_worker = Post_worker(self.ses)
        es_worker = ES_worker(self.es_client)
        await post_worker.del_post(id)
        await self.ses.commit()

        await es_worker.delete_from_index_by_id(id)

        ...

    async def search_document_by_query(self, query: str) -> list[correct_document]:
        es_worker = ES_worker(self.es_client)
        vars: list = (await es_worker.search_by_query(query))['hits']['hits']
        vars.sort(key=lambda el: el['_score'], reverse=True)
        posts_ids = [el['_id'] for el in vars]
        response = []
        
        for post_id in posts_ids:
            response.append(await self.__create_post_rubric_response(post_id))

        response.sort(key=lambda el: el.created_date)
        return response[:20]






