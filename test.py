from service.service import DocumentService
import asyncio
import csv
from db.db_model import db_helper
from dto.dto import new_document, correct_document
from db.db_model import Base, db_helper
from datetime import datetime

DEL_TABLE = str.maketrans('','',"[]',]")

async def dbc():
    async for ses in db_helper.get_session():
        doc_worker = DocumentService(ses)

        await doc_worker.insert_document(new_document(text='123', raw_date=datetime.now()))


asyncio.run(dbc())