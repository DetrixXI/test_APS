import pytest
from datetime import datetime

from sqlalchemy import insert, select

from db.models import Posts, Rubrics, posts_rubrics_relation as prr
from service.service import Doc_Delete
from fastapi import HTTPException

@pytest.mark.asyncio
async def test_delete_post_keeps_shared_rubric(test_ses, test_es):
    """пост 1 и пост 2 делят рубрику, удаляем пост 1 - рубрика остаётся"""
    r1 = Rubrics(rubric_code="shared")
    test_ses.add(r1)
    await test_ses.flush()

    post1 = Posts(text="Первый", created_date=datetime(2026, 1, 1))
    post2 = Posts(text="Второй", created_date=datetime(2026, 1, 2))
    test_ses.add_all([post1, post2])
    await test_ses.flush()

    await test_ses.execute(insert(prr).values(post_id=post1.id, rubric_id=r1.id))
    await test_ses.execute(insert(prr).values(post_id=post2.id, rubric_id=r1.id))
    await test_ses.commit()

    await test_es.index(index="test_posts", id=str(post1.id), body={"text": "Первый"}, refresh=True)
    await test_es.indices.refresh(index="test_posts")

    service = Doc_Delete(ses=test_ses, es_client=test_es)
    await service.delete_document_by_id(post1.id)

    # рубрика жива
    rubric = await test_ses.execute(select(Rubrics).where(Rubrics.id == r1.id))
    assert rubric.scalar() is not None

    # пост удалён
    post = await test_ses.execute(select(Posts).where(Posts.id == post1.id))
    assert post.scalar() is None

    # связь удалена
    links = await test_ses.execute(select(prr).where(prr.c.post_id == post1.id))
    assert len(links.all()) == 0

@pytest.mark.asyncio
async def test_delete_post_removes_orphan_rubric(test_ses, test_es):
    """пост - единственный с этой рубрикой, удаляем пост - рубрика тоже удаляется"""
    r1 = Rubrics(rubric_code="unique")
    post = Posts(text="Единственный", created_date=datetime(2026, 1, 1))
    test_ses.add_all([r1, post])
    await test_ses.flush()
    await test_ses.execute(insert(prr).values(post_id=post.id, rubric_id=r1.id))
    await test_ses.commit()

    await test_es.index(index="test_posts", id=str(post.id), body={"text": "Единственный"})
    await test_es.indices.refresh(index="test_posts")

    service = Doc_Delete(ses=test_ses, es_client=test_es)
    await service.delete_document_by_id(post.id)

    rubric = await test_ses.execute(select(Rubrics).where(Rubrics.id == r1.id))
    assert rubric.scalar() is None

@pytest.mark.asyncio
async def test_delete_nonexistent_post(test_ses, test_es):
    """удаляем несуществующий пост"""
    service = Doc_Delete(ses=test_ses, es_client=test_es)
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_document_by_id(9999)
    assert exc_info.value.status_code == 404

@pytest.mark.asyncio
async def test_delete_idempotent_es_already_empty(test_ses, test_es):
    """es уже не имеет документа (предыдущий вызов удалил или упала бд) - повтор работает"""
    post = Posts(text="Тест", created_date=datetime(2026, 1, 1))
    test_ses.add(post)
    await test_ses.commit()

    # не индексируем в es - имитируем, что уже удалён

    service = Doc_Delete(ses=test_ses, es_client=test_es)
    result = await service.delete_document_by_id(post.id)
    assert result["Success"] is True

    # пост удалён из бд
    deleted = await test_ses.execute(select(Posts).where(Posts.id == post.id))
    assert deleted.scalar() is None

@pytest.mark.asyncio
async def test_delete_post_mixed_rubrics(test_ses, test_es):
    """пост имеет 3 рубрики: 1 общая с другим постом, 2 уникальные"""
    shared = Rubrics(rubric_code="shared")
    uniq1 = Rubrics(rubric_code="uniq1")
    uniq2 = Rubrics(rubric_code="uniq2")
    post1 = Posts(text="Первый", created_date=datetime(2026, 1, 1))
    post2 = Posts(text="Второй", created_date=datetime(2026, 1, 2))
    test_ses.add_all([shared, uniq1, uniq2, post1, post2])
    await test_ses.flush()

    await test_ses.execute(insert(prr).values(post_id=post1.id, rubric_id=shared.id))
    await test_ses.execute(insert(prr).values(post_id=post1.id, rubric_id=uniq1.id))
    await test_ses.execute(insert(prr).values(post_id=post1.id, rubric_id=uniq2.id))
    await test_ses.execute(insert(prr).values(post_id=post2.id, rubric_id=shared.id))
    await test_ses.commit()

    await test_es.index(index="test_posts", id=str(post1.id), body={"text": "Первый"})
    await test_es.indices.refresh(index="test_posts")

    service = Doc_Delete(ses=test_ses, es_client=test_es)
    await service.delete_document_by_id(post1.id)

    alive = (await test_ses.execute(select(Rubrics.rubric_code))).scalars().all()
    assert "shared" in alive
    assert "uniq1" not in alive
    assert "uniq2" not in alive


