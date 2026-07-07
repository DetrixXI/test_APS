from fastapi import FastAPI 
import uvicorn

from routers.routers import main_router
from settings import Settings
from dependencies.dependencies import lifespan

app = FastAPI(lifespan=lifespan)

app.include_router(router=main_router)

if __name__ == "__main__":
    uvicorn.run("app:app", reload=True,
                host=Settings.HOST,
                port=Settings.PORT)
