from fastapi import Depends, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from elasticsearch import AsyncElasticsearch

from service.service import Doc_Search, Doc_Delete
from db.db_model import db_helper
from es.es_start import es_helper

main_router= APIRouter(prefix="/test_task")

@main_router.get("/search",
                 summary = "Производит поиск по словам из запроса по индексу в эластике, ответ ограничен топ-20 записями по score. Сам топ-20 отсорирован по дате")
async def search(query: str,
                 ses: AsyncSession = Depends(db_helper.get_session),
                 es_client: AsyncElasticsearch = Depends(es_helper.get_es_client)):
    doc_service = Doc_Search(ses=ses, es_client=es_client)
    res = await doc_service.search_document_by_query(query)
    return {"result": res} if res != [] else {'result': "По запросу ничего не найдено"}

@main_router.delete("/del_by_id", 
                    summary = "Удаляет записm из индекс эластика и из БД")
async def delete(id: int,
                 ses: AsyncSession = Depends(db_helper.get_session),
                 es_client: AsyncElasticsearch = Depends(es_helper.get_es_client)):
    doc_service = Doc_Delete(ses=ses, es_client=es_client)
    await doc_service.delete_document_by_id(post_id=id)
    return {"Success": True}


