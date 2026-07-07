from elasticsearch import AsyncElasticsearch, helpers

from es.es_start import es_helper
from dto.dto import post_from_db


class ES_worker():
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def bulk_insert_to_index(self, posts: dict):
        """posts -> {post.id: post.text}"""
        tasks = []
        for id, text in posts.items():
            tasks.append(
                {"_index": es_helper.index_name,
                 "_source": {
                     'text': text
                            },
                 "_id": id
                 }
            )
        await helpers.async_bulk(client=self.es_client, 
                                                  actions=tasks, 
                                                  chunk_size=500)

        ...

    async def insert_to_index(self, post: post_from_db):
        await self.es_client.index(index=es_helper.index_name,
                                   id = post.id,
                                   document={"text": post.text})
        ...

    async def search_by_query(self, q:str):
        query = {
            "query":{
                "multi_match":{
                        "query": q,
                        "operator": "and",
                        "fields": ["text^2", "text.prefix"],
                        "type": "best_fields",
                    }
                },
                "terminate_after":20,
                "min_score": 8
            }
        res = await self.es_client.search(index=es_helper.index_name, body=query)
        return res

    async def delete_from_index_by_id(self, id: int):
        await self.es_client.delete(index=es_helper.index_name, id=id)
        
        


