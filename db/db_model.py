from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine, AsyncSession
from db.settings import Settings

DB_URL = Settings.get_db_url()

class DB_helper():
    def __init__(self):
        self.engine = create_async_engine(url= Settings.get_db_url(),
                                    pool_size= 3, max_overflow= 5)
        self.session_gen = async_sessionmaker(bind=self.engine, autocommit=False,
                                            autoflush=False, expire_on_commit=False)

    async def get_session(self):
        async with self.session_gen() as ses:
            yield ses

db_helper = DB_helper()

class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ...




