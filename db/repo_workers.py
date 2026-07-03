from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import insert, delete, update, select, and_
import asyncio

from models.models import Posts, Rubrics, posts_rubrics_relation as prr
from dto.dto import New_rubric_dto, New_post_dto

class Rubric_worker():
    def __init__(self, ses: AsyncSession):
        self.ses = ses

    async def __execute(self, stm):
        return (await self.ses.execute(stm))
    
################
# Insert-ручкa #
################
    async def insert_rubric(self, rubric: New_rubric_dto) -> Rubrics:
        try:
            stm = insert(Rubrics).values(rubric_code = rubric.rubric_code).returning(Rubrics)   
            return (await self.__execute(stm)).scalar()
        except IntegrityError as e:
            stm = select(Rubrics).where(Rubrics.rubric_code == rubric.rubric_code)
            return (await self.__execute(stm)).scalar()
    
################
# Селект-ручкa #
################
    async def select_rubric(self, id: int) -> Rubrics:
        stm = select(Rubrics).where(Rubrics.id == id)
        return await self.__execute(stm)

################
# Delete-ручки #
################ 
    async def del_rubric(self, id: int):
        stm = delete(Rubrics).where(Rubrics.id == id)
        await self.__execute(stm)
    
class Post_worker():
    def __init__(self, ses: AsyncSession):
        self.ses = ses

    async def __execute(self, stm):
        return (await self.ses.execute(stm))
    
################
# Insert-ручкa #
################
    async def insert_post(self, post: New_post_dto) -> Posts:
        stm = insert(Posts).values(text = post.text, created_date = post.created_date).returning(Posts)   
        return (await self.__execute(stm)).scalar()
    
################
# Селект-ручкa #
################
    async def select_post(self, id: int) -> Posts:
        stm = select(Posts).where(Posts.id == id)
        return await self.__execute(stm)

################
# Delete-ручки #
################ 
    async def del_post(self, id: int):
        stm = delete(Posts).where(Posts.id == id)
        await self.__execute(stm)

class Prr_worker():
    def __init__(self, ses: AsyncSession):
        self.ses = ses

    async def __execute(self, stm):
        return (await self.ses.execute(stm))
    
################
# Insert-ручкa #
################
    async def insert_prr_relation(self, post_id: int, rubric_id: int):
        stm = insert(prr).values(post_id = post_id, rubric_id = rubric_id).returning(prr)   
        return (await self.__execute(stm)).scalar()
    
################
# Селект-ручкa #
################
    async def select_rel_by_pid(self, post_id: int):
        stm = select(prr).where(prr.c.post_id == post_id)
        return await self.__execute(stm)

    async def select_rel_by_rid(self, rubric_id: int):
        stm = select(prr).where(prr.c.rubric_id == rubric_id)
        return await self.__execute(stm)

################
# Delete-ручки #
################ 
    async def del_rel(self, post_id: int, rubric_id: int):
        stm = delete(Posts).where(and_(prr.c.rubric_id == rubric_id, prr.c.post_id == post_id))
        await self.__execute(stm)