import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime

from sqlalchemy import insert


from db.models import Posts, Rubrics, posts_rubrics_relation as prr
from service.service import Doc_Search
from elasticsearch.exceptions import TransportError
from fastapi import HTTPException

from es.es_start import es_helper


class FakeESWorker:

    def __init__(self, fail_times=0):
        self._fail_times = fail_times
        self._call_count = 0

    async def search_by_query(self, query):
        self._call_count += 1
        if self._call_count <= self._fail_times:
            raise TransportError(500, "ES unavailable")
        return {'hits': {'hits': [{'_id': '1'}]}}


# Поиск multiple rubrics
@pytest.mark.asyncio
async def test_search_multiple_rubrics(test_ses, test_es):
    post = Posts(text="Привет мир", created_date=datetime(2026, 1, 1))
    test_ses.add(post)
    await test_ses.flush()

    rubrics = [Rubrics(rubric_code="news"), Rubrics(rubric_code="sport"), Rubrics(rubric_code="tech")]
    test_ses.add_all(rubrics)
    await test_ses.flush()

    for r in rubrics:
        await test_ses.execute(insert(prr).values(post_id=post.id, rubric_id=r.id))
    await test_ses.commit()

    await test_es.index(index=es_helper.index_name, id=str(post.id), body={"text": "Привет мир"})
    await test_es.indices.refresh(index=es_helper.index_name)

    service = Doc_Search(ses=test_ses, es_client=test_es)
    result = list(await service.search_document_by_query("Привет"))

    assert len(result) == 1

# Пустой результат из es
@pytest.mark.asyncio
async def test_search_no_results(test_ses, test_es):
    """es ничего не нашёл => пустой список"""
    service = Doc_Search(ses=test_ses, es_client=test_es)
    result = await service.search_document_by_query("несуществующий текст")
    assert result == []

# cортировка по дате
@pytest.mark.asyncio
async def test_search_sorted_by_date(test_ses, test_es):
    """результаты отсортированы по created_date"""
    dates = [datetime(2026, 3, 1), datetime(2026, 1, 1), datetime(2026, 2, 1)]
    for i, date in enumerate(dates):
        post = Posts(text=f"Тест {i}", created_date=date)
        test_ses.add(post)
        await test_ses.flush()
        await test_es.index(index=es_helper.index_name, id=str(post.id), body={"text": f"Тест {i}"})
        await test_ses.execute(insert(prr).values(
            post_id=post.id, rubric_id=(await test_ses.execute(
                insert(Rubrics).values(rubric_code=f"r{i}").returning(Rubrics.id)
            )).scalar()
        ))
    await test_ses.commit()
    await test_es.indices.refresh(index=es_helper.index_name)

    service = Doc_Search(ses=test_ses, es_client=test_es)
    result = list(await service.search_document_by_query("Тест"))

    assert len(result) == 3
    assert result[0]["created_date"] < result[1]["created_date"] < result[2]["created_date"]

# несколько постов с разными рубриками
@pytest.mark.asyncio

@pytest.mark.asyncio
async def test_search_multiple_posts_different_rubrics(test_ses, test_es):
    post1 = Posts(text="Первый пост", created_date=datetime(2026, 1, 1))
    post2 = Posts(text="Второй пост", created_date=datetime(2026, 1, 2))
    test_ses.add_all([post1, post2])
    await test_ses.flush()

    r1 = Rubrics(rubric_code="alpha")
    r2 = Rubrics(rubric_code="beta")
    r3 = Rubrics(rubric_code="gamma")
    test_ses.add_all([r1, r2, r3])
    await test_ses.flush()

    await test_ses.execute(insert(prr).values(post_id=post1.id, rubric_id=r1.id))
    await test_ses.execute(insert(prr).values(post_id=post1.id, rubric_id=r2.id))
    await test_ses.execute(insert(prr).values(post_id=post2.id, rubric_id=r3.id))
    await test_ses.commit()

    await test_es.index(index=es_helper.index_name, id=str(post1.id), body={"text": "Первый пост"})
    await test_es.index(index=es_helper.index_name, id=str(post2.id), body={"text": "Второй пост"})
    await test_es.indices.refresh(index=es_helper.index_name)

    service = Doc_Search(ses=test_ses, es_client=test_es)
    result = list(await service.search_document_by_query("пост"))  # ← list() вместо dict_values

    # диагностика: если результат пустой — увидим, что ES вернул
    assert len(result) > 0, "ES ничего не нашёл — проверь query в ES_worker"

    post1_result = next((r for r in result if r["post_id"] == post1.id), None)
    post2_result = next((r for r in result if r["post_id"] == post2.id), None)

    assert post1_result is not None, "Пост 1 не найден в результате"
    assert post2_result is not None, "Пост 2 не найден в результате"

    assert set(post1_result["rubric_codes"]) == {"alpha", "beta"}
    assert set(post2_result["rubric_codes"]) == {"gamma"}

# retry при недоступности es
@pytest.mark.asyncio
async def test_search_es_retry_then_success(test_ses):
    """es падает 2 раза, на 3-й отвечает - поиск успешен"""
    fake_worker = FakeESWorker(fail_times=2)

    service = Doc_Search(ses=test_ses, es_client=None)
    # подменяем уже созданный ES_worker напрямую
    service.es_client = fake_worker

    with patch('service.service.asyncio.sleep', new_callable=AsyncMock):
        result = await service.search_document_by_query("тест")

    assert fake_worker._call_count == 3

# es падает все 3 раза - error
@pytest.mark.asyncio
async def test_search_es_all_retries_fail(test_ses):
    fake_worker = FakeESWorker(fail_times=99)  # всегда падает

    service = Doc_Search(ses=test_ses, es_client=None)
    service.es_client = fake_worker

    with patch('service.service.asyncio.sleep', new_callable=AsyncMock):
        with pytest.raises(HTTPException) as exc_info:
            await service.search_document_by_query("тест")

    assert exc_info.value.status_code == 504


