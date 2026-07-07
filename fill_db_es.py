import asyncio
from service.service import DocumentService
from db.db_model import db_helper
from es.es_start import es_helper
from settings import Settings
from pathlib import Path

db_path = Path(Settings.DB_SQL_URL)

DEL_TABLE = str.maketrans('','',"[]',]")

async def ins_bulk():
    async for ses in db_helper.get_session():
        async for es_client in es_helper.get_es_client():
            if await es_client.indices.exists(index=es_helper.index_name):
                await es_client.indices.delete(index=es_helper.index_name)
            await es_client.indices.create(index=es_helper.index_name, body=es_helper.body)  
            doc_worker = DocumentService(ses, es_client)
            await doc_worker.bulk_insertion_documents('posts.csv')

def start():
    print("заполнение бд и индекса")
    asyncio.run(ins_bulk())
    print("бд и индекс заполнены")

start()


      