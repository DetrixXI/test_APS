from pydantic import BaseModel
from datetime import datetime

class New_rubric_dto(BaseModel):
    rubric_code: str

class Rubric_dto(New_rubric_dto):
    id: int

class New_post_dto(BaseModel):
    text: str
    created_date: datetime

class new_document(BaseModel):
    text: str    
    raw_date: datetime
    raw_rubric_code: str = "['code_1', 'code_2', ]"

class correct_document(BaseModel):
    text: str    
    created_date: datetime
    rubric_codes: list[str]