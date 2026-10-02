from fastapi import FastAPI 
import uvicorn
import logging
from pathlib import Path
import sys

from routers.routers import main_router
from settings import Settings



def setup_logging():
    log_file = Path("logs") / "app.log"
    log_file.parent.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        handlers=[
            # logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )

app = FastAPI()

app.include_router(router=main_router)

if __name__ == "__main__":
    setup_logging()
    uvicorn.run("app:app", reload=True,
                host=Settings.HOST,
                port=Settings.PORT)
