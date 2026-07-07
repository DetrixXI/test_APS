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
    raw_date: datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raw_rubric_code: list[str]

class correct_document(BaseModel):
    text: str    
    created_date: datetime
    rubric_codes: list[str]

class response_document(correct_document):
    id: int

class post_from_db(BaseModel):
    id: int
    text: str

