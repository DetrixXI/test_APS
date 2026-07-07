from fastapi import Depends, APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from elasticsearch import AsyncElasticsearch, NotFoundError

from service.service import DocumentService
from db.db_model import db_helper
from dependencies.dependencies import get_es_client
from dto.dto import new_document

main_router= APIRouter(prefix="/test_task")

@main_router.get("/search",
                 summary = "Производит поиск по словам из запроса по индексу в эластике, ответ ограничен 20 записями")
async def search(query: str,
                 ses: AsyncSession = Depends(db_helper.get_session),
                 es_client: AsyncElasticsearch = Depends(get_es_client)):
    doc_service = DocumentService(ses=ses, es_client=es_client)
    res = await doc_service.search_document_by_query(query)
    return {"result": res} if res != [] else {'result': "По запросу ничего не найдено"}

@main_router.delete("/del_by_id", 
                    summary = "Удаляет записи из posts и posts_rubrics_relation по id документа. Так же удаляет документ из индекса эластика")
async def search(id: int,
                 ses: AsyncSession = Depends(db_helper.get_session),
                 es_client: AsyncElasticsearch = Depends(get_es_client)):
    doc_service = DocumentService(ses=ses, es_client=es_client)
    try:
        await doc_service.delete_document_by_pid(id=id)
        return {"Success": True}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Файл не найден")

@main_router.put("/insert_doc",
                 summary = "Добавляет документ в бд и индекс эластика")
async def insert_document(document: new_document, 
                          ses: AsyncSession = Depends(db_helper.get_session),
                        es_client: AsyncElasticsearch = Depends(get_es_client)):
    doc_service = DocumentService(ses=ses, es_client=es_client)
    await doc_service.insert_document(document)
    return {"Success": True}



