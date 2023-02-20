import asyncio
from logging.config import dictConfig

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from starlette.middleware import Middleware

from asgi_correlation_id.middleware import CorrelationIdMiddleware


@pytest.fixture(autouse=True, scope='session')
def _configure_logging():
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'filters': {
            'correlation_id': {'()': 'asgi_correlation_id.CorrelationIdFilter'},
            'celery_tracing': {'()': 'asgi_correlation_id.CeleryTracingIdsFilter'},
        },
        'formatters': {
            'full': {
                'class': 'logging.Formatter',
                'datefmt': '%H:%M:%S',
                'format': '[%(correlation_id)s] [%(celery_parent_id)s-%(celery_current_id)s] %(message)s',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'filters': ['correlation_id', 'celery_tracing'],
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
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope='module')
async def client() -> AsyncClient:
    async with AsyncClient(app=default_app, base_url='http://test') as client:
        yield client
