from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import insert, delete, update, select, and_, outerjoin
import asyncio

from models.models import Posts, Rubrics, posts_rubrics_relation as prr
from dto.dto import New_rubric_dto, New_post_dto

class base_worker():
    def __init__(self, ses:AsyncSession):
        self.ses = ses

    async def execute(self, stm):
        return (await self.ses.execute(stm))


class Rubric_worker(base_worker):
    def __init__(self, ses: AsyncSession):
        super().__init__(ses)

################
# Insert-ручкa #
################
    async def insert_rubric(self, rubric: New_rubric_dto|list[dict]) -> Rubrics:
        try:
            if isinstance(rubric, list):
                stm = insert(Rubrics).values(rubric).returning(Rubrics)
                return (await self.execute(stm)).scalars().all() 
            else:
                stm = insert(Rubrics).values(rubric_code = rubric.rubric_code).returning(Rubrics)   
            return (await self.execute(stm)).scalar()
        except IntegrityError as e:
            stm = select(Rubrics).where(Rubrics.rubric_code == rubric.rubric_code)
            return (await self.execute(stm)).scalar()
    
################
# Селект-ручкa #
################
    async def select_rubric(self, id: int) -> Rubrics:
        stm = select(Rubrics).where(Rubrics.id == id)
        return (await self.execute(stm)).scalar()

################
# Delete-ручки #
################ 
    async def del_rubric(self, id: int):
        stm = delete(Rubrics).where(Rubrics.id == id)
        await self.execute(stm)
    
class Post_worker(base_worker):
    def __init__(self, ses: AsyncSession):
        super().__init__(ses)
    
################
# Insert-ручкa #
################
    async def insert_post(self, post: New_post_dto|list[dict]) -> Posts:
        if isinstance(post, New_post_dto):
            stm = insert(Posts).values(text = post.text, created_date = post.created_date).returning(Posts)
            return (await self.execute(stm)).scalar()
        else:
            stm = insert(Posts).values(post).returning(Posts)
            return (await self.execute(stm)).scalars().all()
    
################
# Селект-ручкa #
################
    async def select_post(self, id: int) -> Posts:
        stm = select(Posts).where(Posts.id == id)
        return (await self.execute(stm)).scalar()

    async def selet_all_posts_ids(self) -> list[int]:
        stm = select(Posts.id)
        return (await self.execute(stm)).scalars().all()

    async def select_all_posts(self) -> list[Posts]:
        stm = select(Posts)
        return (await self.execute(stm)).scalars().all()

################
# Delete-ручки #
################ 
    async def del_post(self, id: int):
        stm = delete(Posts).where(Posts.id == id)
        await self.execute(stm)

class Prr_worker(base_worker):
    def __init__(self, ses: AsyncSession):
        super().__init__(ses)
    
################
# Insert-ручкa #
################
    async def insert_prr_relation(self, post_rubric_struct: list|dict):
        """list[post_id, rubric_id] or dict{'post_id':int, 'rubric_id':int}"""
        if isinstance(post_rubric_struct[0], dict):
            stm = insert(prr).values(post_rubric_struct).returning(prr)   
            return (await self.execute(stm)).scalars().all()
        else:
            stm = insert(prr).values(post_id = post_rubric_struct[0], rubric_id = post_rubric_struct[1]).returning(prr)   
            return (await self.execute(stm)).scalar()
            
    
################
# Селект-ручкa #
################
    async def select_rels_by_pid(self, post_id: int):
        stm = select(prr.c.rubric_id).where(prr.c.post_id == post_id)
        return (await self.execute(stm)).scalars().all()
    
    async def select_posts_and_rubrics(self, post_ids: list[int]):
        stm = select(prr, Posts.text, Posts.created_date, Rubrics.rubric_code
                ).select_from(
                    outerjoin(prr, Posts, prr.c.post_id == Posts.id)
                    ).outerjoin(Rubrics, prr.c.rubric_id == Rubrics.id
                    ).where(prr.c.post_id.in_(post_ids))
        return (await self.execute(stm)).mappings().all()

################
# Delete-ручки #
################ 
    async def del_rel(self, post_id: int, rubric_id: int):
        stm = delete(prr).where(and_(prr.c.rubric_id == rubric_id, prr.c.post_id == post_id))
        await self.execute(stm)

    async def del_rels_by_act_pids(self, posts_ids: list[int]):
        stm = delete(prr).where(prr.c.post_id.not_in(posts_ids))
        await self.execute(stm)