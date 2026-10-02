import pytest
from datetime import datetime

from db.models import Posts, Rubrics
from service.service import Doc_Search, Doc_Delete

@pytest.mark.asyncio
async def test_handler_search_success(test_client):
    # нужно предварительно заполнить БД и ES
    response = await test_client.get("/test_task/search", params={"query": "Привет"})
    assert response.status_code == 200
    assert "result" in response.json()

@pytest.mark.asyncio
async def test_handler_search_not_found(test_client):
    response = await test_client.get("/test_task/search", params={"query": "абракадабра"})
    assert response.status_code == 200
    assert response.json()["result"] == "По запросу ничего не найдено"

@pytest.mark.asyncio
async def test_handler_delete_success(test_client, test_ses):
    post = Posts(text="Удаляемый", created_date=datetime(2026, 1, 1))
    test_ses.add(post)
    await test_ses.commit()
    # индексируем в es...

    response = await test_client.delete("/test_task/del_by_id", params={"id": post.id})
    assert response.status_code == 200
    assert response.json()["Success"] is True

@pytest.mark.asyncio
async def test_handler_delete_not_found(test_client):
    response = await test_client.delete("/test_task/del_by_id", params={"id": 9999})
    assert response.status_code == 404