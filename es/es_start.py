from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import TransportError, ConnectionError
from settings import Settings
import asyncio

class ES_helper():
    def __init__(self):
        self.index_name = "posts"
        self.body = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                "filter": {
                    "rus_stop": {
                    "type": "stop",
                    "stopwords": "_russian_"
                    },
                    "rus_stemmer": {
                    "type": "stemmer",
                    "language": "russian"
                    }
                },
                "tokenizer": {
                    "edge_ngram_tokenizer": {
                    "type": "edge_ngram",
                    "min_gram": 4,
                    "max_gram": 10,
                    "token_chars": ["letter", "digit"]
                    }
                },
                "analyzer": {
                    "rus_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "rus_stop", "rus_stemmer"]
                    },
                    "pref_analyzer": {
                    "type": "custom",
                    "tokenizer": "edge_ngram_tokenizer",
                    "filter": ["lowercase"]
                    }
                }
                }
            },
            "mappings": {
                "properties": {
                "text": {
                    "type": "text",
                    "analyzer": "rus_analyzer",
                    "fields": {
                    "prefix": {
                        "type": "text",
                        "analyzer": "pref_analyzer"
                    }
                    }
                }
                }
            }
            }

    async def get_es_client(self):
        async with AsyncElasticsearch(Settings.get_es_url()) as es_client:
            for i in range(10):   
                try:
                    await es_client.cluster.health()
                    continue
                except (TransportError, ConnectionError) as e:
                    print('ожидание AsyncElasticsearch-клиента')
                    await asyncio.sleep(7)
            yield es_client

es_helper = ES_helper()
    