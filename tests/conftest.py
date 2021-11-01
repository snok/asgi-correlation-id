import asyncio
from logging.config import dictConfig

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from starlette.middleware import Middleware

from asgi_correlation_id import celery_tracing_id_filter, correlation_id_filter
from asgi_correlation_id.middleware import CorrelationIdMiddleware


@pytest.fixture(autouse=True, scope='session')
def _configure_logging():
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'filters': {
            'correlation_id': {'()': correlation_id_filter()},
            'celery_tracing': {'()': celery_tracing_id_filter()},
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


app = FastAPI(middleware=[Middleware(CorrelationIdMiddleware)])


@pytest.fixture(scope='session', autouse=True)
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='module')
async def client() -> AsyncClient:
    async with AsyncClient(app=app, base_url='http://test') as client:
        yield client
