import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class all_Settings(BaseSettings):
    DB_SQL_URL: str

    model_config = SettingsConfigDict(env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), "conf.env"))

    def get_db_url(self):
        return (f"sqlite+aiosqlite:///{self.DB_SQL_URL}")

Settings = all_Settings()