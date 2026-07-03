import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import csv

from models.models import posts_rubrics_relation, Posts, Rubrics
from dto.dto import new_document, New_rubric_dto, New_post_dto, correct_document
from db.repo_workers import Rubric_worker, Post_worker, Prr_worker

DEL_TABLE = str.maketrans('','',"[]',]")

class DocumentService():
    def __init__(self, ses: AsyncSession):
        self.ses = ses

    @staticmethod
    async def __create_correct_document(document: list[str]) -> correct_document:
        print([document[1]])
        suit_date = datetime.strptime(document[1], "%Y-%m-%d %H:%M:%S") if not isinstance(document[1], datetime) else document[1]
        suit_rubrics = document[2].translate(DEL_TABLE).split(' ')
        text = document[0]
        return correct_document(text=text, created_date=suit_date, rubric_codes=suit_rubrics)

    async def bulk_insertion_documents(self, adress_csv: str):
        with open(adress_csv, 'r', encoding='utf-8') as f:
            data = csv.reader(f, delimiter=',')
            next(data)
            for document in data:
                document = await self.__create_correct_document(document)

                post = await Post_worker(self.ses).insert_post(New_post_dto(text=document.text, created_date=document.created_date))
                rubric_worker = Rubric_worker(self.ses)
                prr_worker = Prr_worker(self.ses)

                for rubric in document.rubric_codes:
                    rubric = await rubric_worker.insert_rubric(New_rubric_dto(rubric_code=rubric))
                    await self.ses.flush()
                    await prr_worker.insert_prr_relation(post.id, rubric.id)
            
        await self.ses.commit()

    async def insert_document(self, new_doc: new_document):
        new_doc = list(new_doc.model_dump().values())
        document = await self.__create_correct_document(new_doc)
        rubrics = [Rubrics(rubric_code = el) for el in document.rubric_codes]
        post = Posts(text=document.text, created_date=document.created_date, rubrics=rubrics)
        self.ses.add(post)
        await self.ses.commit()
        
    async def delete_document_by_pid(self, ses: AsyncSession):
        

        
        ...






