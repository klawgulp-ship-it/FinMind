from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.session import close_pool, create_pool
from app.routes.user import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_pool()
    yield
    await close_pool()


app = FastAPI(title="GDPR-Ready API", lifespan=lifespan)

app.include_router(user_router)
