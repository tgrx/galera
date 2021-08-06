import asyncio
from typing import AsyncGenerator

import httpx
import pytest

from framework.config import settings
from framework.logging import logger
from main import db
from main.custom_types import UserT
from main.db import Base
from main.db import begin_session
from main.webapp import application

TIMEOUT = 4


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()

    yield loop


@pytest.fixture(scope="function")
async def asgi_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        app=application,
        base_url="http://asgi",
        timeout=TIMEOUT,
    ) as client:
        yield client


@pytest.fixture(scope="function")
async def web_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        base_url=settings.TEST_SERVICE_URL,
        timeout=TIMEOUT,
    ) as client:
        yield client


@pytest.fixture(scope="function", autouse=True)
async def clean_db() -> AsyncGenerator[None, None]:
    yield

    async with begin_session() as session:
        for table in Base.metadata.tables:
            logger.debug(f"truncating table {table}")
            await session.execute(f"truncate {table} cascade;")


@pytest.fixture(scope="function")
async def admin() -> AsyncGenerator[UserT, None]:
    obj = await db.create_user(
        name="admin",
        password="admin",
        is_admin=True,
    )

    user = UserT.from_orm(obj)

    yield user
