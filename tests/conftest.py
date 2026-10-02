import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from elasticsearch import AsyncElasticsearch


from db.models import Base, Posts, Rubrics, posts_rubrics_relation as prr
from app import app
from db.db_model import db_helper
from es.es_start import es_helper

@pytest_asyncio.fixture
async def test_engine():
    """тестовая бд в памяти"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, poolclass=StaticPool,)

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_ses(test_engine):
    """сессия с откатом после каждого теста"""
    async_session = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as ses:
        yield ses
        await ses.rollback()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def cleanup_es_clients():
    """закрывает все es-клиенты после тестов"""
    yield
    if hasattr(es_helper, 'es_client') and es_helper.es_client:
        await es_helper.es_client.close()

@pytest_asyncio.fixture
async def test_es():
    es = AsyncElasticsearch("http://localhost:9200")

    await es.indices.delete(index=es_helper.index_name, ignore_unavailable=True)

    await es.indices.create(
        index=es_helper.index_name,
        body=es_helper.body
    )
    
    yield es

    await es.indices.delete(index=es_helper.index_name, ignore_unavailable=True)
    await es.close()


@pytest_asyncio.fixture
async def test_client(test_engine, test_es):
    """HTTP-клиент для тестирования ручек"""
    async def override_session():
        async_session = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as ses:
            yield ses

    app.dependency_overrides[db_helper.get_session] = override_session
    app.dependency_overrides[es_helper.get_es_client] = lambda: test_es

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()