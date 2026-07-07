import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class all_Settings(BaseSettings):
    DB_SQL_URL: str = "./posts_db.db"
    ES_URL: str = "elasticsearch:9200"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ES_INDEX: str = "ES_index"
    

    model_config = SettingsConfigDict(env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

    def get_db_url(self):
        return (f"sqlite+aiosqlite:///{self.DB_SQL_URL}")

    def get_es_url(self):
        return(f"http://{self.ES_URL}")
        

Settings = all_Settings()