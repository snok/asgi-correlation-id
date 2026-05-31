import asyncio
from collections.abc import AsyncGenerator
from logging.config import dictConfig

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.middleware import Middleware

from asgi_correlation_id.middleware import CorrelationIdMiddleware


@pytest.fixture(autouse=True, scope='session')
def _configure_logging():
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'filters': {
            'correlation_id': {'()': 'asgi_correlation_id.CorrelationIdFilter'},
        },
        'formatters': {
            'full': {
                'class': 'logging.Formatter',
                'datefmt': '%H:%M:%S',
                'format': '[%(correlation_id)s] %(message)s',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'filters': ['correlation_id'],
                'formatter': 'full',
            },
        },
        'loggers': {
            # project logger
            'asgi_correlation_id': {
                'handlers': ['console'],
                'level': 'DEBUG',
                'propagate': True,
            },
        },
    }
    dictConfig(LOGGING)


TRANSFORMER_VALUE = 'some-id'

default_app = FastAPI(middleware=[Middleware(CorrelationIdMiddleware)])
update_request_header_app = FastAPI(middleware=[Middleware(CorrelationIdMiddleware, update_request_header=True)])
no_validator_or_transformer_app = FastAPI(
    middleware=[Middleware(CorrelationIdMiddleware, validator=None, transformer=None)]
)
transformer_app = FastAPI(middleware=[Middleware(CorrelationIdMiddleware, transformer=lambda a: a * 2)])
generator_app = FastAPI(middleware=[Middleware(CorrelationIdMiddleware, generator=lambda: TRANSFORMER_VALUE)])


@pytest.fixture(scope='session', autouse=True)
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope='module')
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=default_app), base_url='http://test') as client:
        yield client
