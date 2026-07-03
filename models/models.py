from sqlalchemy import Column, Integer, String, DATETIME, ForeignKey, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from db.db_model import Base


posts_rubrics_relation = Table(
    "posts_rubrics_relation",
    Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id"), primary_key=True),
    Column("rubric_id", Integer, ForeignKey("rubrics.id"), primary_key=True),
)

class Posts(Base):
    __tablename__ = 'posts'

    text: Mapped[str] = mapped_column(String, nullable=False)
    created_date: Mapped[datetime] = mapped_column(DATETIME, nullable=False)
    rubrics: Mapped[list["Rubrics"]] = relationship("Rubrics", 
                                        secondary=posts_rubrics_relation, 
                                        back_populates="posts")

class Rubrics(Base):
    __tablename__ = 'rubrics'

    rubric_code: Mapped[str] = mapped_column(String, nullable=False, index=True, unique=True)
    posts: Mapped[list["Posts"]] = relationship("Posts",
                                     secondary=posts_rubrics_relation,
                                     back_populates="rubrics")


