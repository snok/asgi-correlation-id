import logging
import uuid

import fastapi
import pytest

import asgi_correlation_id
import asgi_correlation_id.context

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True, scope='session')
def _configure_logging():
    """Override conftest"""


@pytest.fixture(autouse=True)
def _reset_log_factory():
    """
    Reset the log record factory to the default as per Python std lib

    By design, instantiating a CorrelationIdMiddleware object has a side effect of modifying the log record factory.
    Since we may have created middleware instances in other tests, we need to undo the side effect before running any
    test.
    """
    logging.setLogRecordFactory(logging.LogRecord)


def test_instantiated_middleware_enriches_subsequent_logs(caplog):
    caplog.set_level(logging.INFO)

    logger.info('Hello, world')
    last_log_record = caplog.records[-1]
    assert last_log_record.msg == 'Hello, world'  # Check it's the record we think it is
    assert not hasattr(last_log_record, 'correlation_id')

    asgi_correlation_id.CorrelationIdMiddleware(app=fastapi.FastAPI())  # Triggers custom log records
    cid = uuid.uuid4().hex
    asgi_correlation_id.context.correlation_id.set(cid)
    logger.info('Hello, world again')

    last_log_record = caplog.records[-1]
    assert last_log_record.msg == 'Hello, world again'  # Check it's the record we think it is
    assert hasattr(last_log_record, 'correlation_id')
    assert last_log_record.correlation_id == cid  # type: ignore[attr-defined]
