from elasticsearch import AsyncElasticsearch, helpers
import logging

from es.es_start import es_helper


logger = logging.getLogger(__name__)

class ES_worker():
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def search_by_query(self, q:str) -> dict:
        query = {
            "query":{
                "multi_match":{
                        "query": q,
                        "operator": "and",
                        "fields": ["text^2", "text.prefix"],
                        "type": "best_fields",
                    }
                },
                'size': 20,
                '_source': False
            }
        res = await self.es_client.search(index=es_helper.index_name, body=query)
        return res

    async def delete_from_index_by_id(self, id: int):
        await self.es_client.delete(index=es_helper.index_name, id=id)
        
        


