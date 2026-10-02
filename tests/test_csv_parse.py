import pytest
from datetime import datetime

from sqlalchemy import insert, select

from db.models import Posts, Rubrics, posts_rubrics_relation as prr
from service.service import CSV_Parse_Service


def test_parse_csv_valid(tmp_path):
    '''парсим валидный csv'''
    csv_content = "text,created_date,rubric_codes\nПривет,2026-01-01 12:00:00,\"['news', 'sport']\"\nМир,2026-01-02 13:00:00,\"['tech']\"\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding='utf-8')

    batches = list(CSV_Parse_Service.parse_csv(str(csv_file)))
    assert len(batches) == 1
    assert len(batches[0]) == 2
    assert batches[0][0][0] == "Привет"
    assert batches[0][0][2] == ['news', 'sport']

def test_parse_csv_invalid_date(tmp_path):
    '''парсим csv с битой датой (должна пропуститься)'''
    csv_content = "text,created_date,rubric_codes\nПривет,НЕ_ДАТА,\"['news']\"\nМир,2026-01-02 13:00:00,\"['tech']\"\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding='utf-8')

    batches = list(CSV_Parse_Service.parse_csv(str(csv_file)))
    assert len(batches[0]) == 1  # только вторая строка
    assert batches[0][0][0] == "Мир"

def test_parse_csv_invalid_rubrics(tmp_path):
    """парсим csv с невалидным списком рубрик"""
    csv_content = "text,created_date,rubric_codes\nПривет,2026-01-01 12:00:00,НЕ_СПИСОК\nМир,2026-01-02 13:00:00,\"['tech']\"\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding='utf-8')

    batches = list(CSV_Parse_Service.parse_csv(str(csv_file)))
    assert len(batches[0]) == 1
    assert batches[0][0][0] == "Мир"

def test_parse_csv_batching(tmp_path):
    """смотрим батчинг, как берется последний"""
    lines = ["text,created_date,rubric_codes\n"]
    for i in range(1200):
        lines.append(f"Текст {i},2026-01-01 12:00:00,\"['r{i}']\"\n")
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("".join(lines), encoding='utf-8')

    batches = list(CSV_Parse_Service.parse_csv(str(csv_file)))
    assert len(batches) == 3
    assert len(batches[0]) == 500
    assert len(batches[1]) == 500
    assert len(batches[2]) == 200

def test_parse_csv_empty(tmp_path):
    """краевой случай - пустой csv"""
    csv_content = "text,created_date,rubric_codes\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding='utf-8')

    batches = list(CSV_Parse_Service.parse_csv(str(csv_file)))
    assert len(batches) == 0

@pytest.mark.asyncio
async def test_fill_bd_inserts_posts_and_rubrics(test_ses):
    """вставка постов и рубрик"""
    batch = [
        ["Текст 1", datetime(2026, 1, 1), ["news", "sport"]],
        ["Текст 2", datetime(2026, 1, 2), ["news", "tech"]],
    ]
    service = CSV_Parse_Service(ses=test_ses, es_client=None)
    result = await service._CSV_Parse_Service__fill_bd(batch)

    assert len(result) == 2

    posts = (await test_ses.execute(select(Posts))).scalars().all()
    assert len(posts) == 2

    rubrics = (await test_ses.execute(select(Rubrics.rubric_code))).scalars().all()
    assert set(rubrics) == {"news", "sport", "tech"}

    # проверяем связи
    rels = (await test_ses.execute(select(prr))).all()
    assert len(rels) == 4  # 2 + 2 рубрики на пост

@pytest.mark.asyncio
async def test_fill_bd_duplicate_rubrics(test_ses):
    """eсли рубрика 'news' уже есть - НЕ создаем новую"""
    test_ses.add(Rubrics(rubric_code="news"))
    await test_ses.commit()

    batch = [["Текст", datetime(2026, 1, 1), ["news", "sport"]]]
    service = CSV_Parse_Service(ses=test_ses, es_client=None)
    await service._CSV_Parse_Service__fill_bd(batch)

    rubrics = (await test_ses.execute(
        select(Rubrics).where(Rubrics.rubric_code == "news")
    )).scalars().all()
    assert len(rubrics) == 1  # не дубликат