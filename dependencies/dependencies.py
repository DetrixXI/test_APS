from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio 

from es.es_start import es_helper
from db.db_model import db_helper
from db.repo_workers import Post_worker, Prr_worker

async def cleanup_prr_table(flag = False):
    while True:
        async for ses in db_helper.get_session():
            post_worker = Post_worker(ses)
            prr_worker = Prr_worker(ses)
            post_ids_act = await post_worker.selet_all_posts_ids()
            await prr_worker.del_rels_by_act_pids(post_ids_act)
        if flag:
            break
        await asyncio.sleep(900)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global es_client
    async for client in es_helper.get_es_client():
        es_client = client
        clean_task = asyncio.create_task(cleanup_prr_table())
        yield
        clean_task.cancel()
        await cleanup_prr_table(flag=True)

async def get_es_client():
    return es_client