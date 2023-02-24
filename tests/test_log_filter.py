import contextvars
from logging import INFO, LogRecord
from uuid import uuid4

import pytest

from asgi_correlation_id import CeleryTracingIdsFilter, CorrelationIdFilter
from asgi_correlation_id.context import celery_current_id, celery_parent_id, correlation_id

# Initialize context variables to obtain reset tokens which we can later use
# when testing application of filter default values.
correlation_id_token: contextvars.Token = correlation_id.set(None)
celery_parent_id_token: contextvars.Token = celery_parent_id.set(None)
celery_current_id_token: contextvars.Token = celery_current_id.set(None)


@pytest.fixture()
def cid():
    """Set and return a correlation ID"""
    cid = uuid4().hex
    correlation_id.set(cid)
    return cid


@pytest.fixture()
def log_record():
    """Create and return an INFO-level log record"""
    return LogRecord(name='', level=INFO, pathname='', lineno=0, msg='Hello, world!', args=(), exc_info=None)


def test_filter_has_uuid_length_attributes():
    filter_ = CorrelationIdFilter(uuid_length=8)
    assert filter_.uuid_length == 8


def test_filter_has_default_value_attributes():
    filter_ = CorrelationIdFilter(default_value='-')
    assert filter_.default_value == '-'


def test_filter_adds_correlation_id(cid: str, log_record: LogRecord):
    filter_ = CorrelationIdFilter()

    assert not hasattr(log_record, 'correlation_id')
    filter_.filter(log_record)
    assert log_record.correlation_id == cid


def test_filter_truncates_correlation_id(cid: str, log_record: LogRecord):
    filter_ = CorrelationIdFilter(uuid_length=8)

    assert not hasattr(log_record, 'correlation_id')
    filter_.filter(log_record)
    assert len(log_record.correlation_id) == 8  # Needs to match uuid_length
    assert cid.startswith(log_record.correlation_id)  # And needs to be the first 8 characters of the id


def test_filter_uses_default_value(cid: str, log_record: LogRecord):
    """
    We expect the filter to set the log record attribute to the default value
    if the context variable is not set.
    """
    filter_ = CorrelationIdFilter(default_value='-')
    correlation_id.reset(correlation_id_token)

    assert not hasattr(log_record, 'correlation_id')
    filter_.filter(log_record)
    assert log_record.correlation_id == '-'


def test_celery_filter_has_uuid_length_attributes():
    filter_ = CeleryTracingIdsFilter(uuid_length=8)
    assert filter_.uuid_length == 8


def test_celery_filter_has_default_value_attributes():
    filter_ = CeleryTracingIdsFilter(default_value='-')
    assert filter_.default_value == '-'


def test_celery_filter_adds_parent_id(cid: str, log_record: LogRecord):
    filter_ = CeleryTracingIdsFilter()
    celery_parent_id.set('a')

    assert not hasattr(log_record, 'celery_parent_id')
    filter_.filter(log_record)
    assert log_record.celery_parent_id == 'a'


def test_celery_filter_adds_current_id(cid: str, log_record: LogRecord):
    filter_ = CeleryTracingIdsFilter()
    celery_current_id.set('b')

    assert not hasattr(log_record, 'celery_current_id')
    filter_.filter(log_record)
    assert log_record.celery_current_id == 'b'


def test_celery_filter_uses_default_value(cid: str, log_record: LogRecord):
    """
    We expect the filter to set the log record attributes to the default value
    if the context variables are not not set.
    """
    filter_ = CeleryTracingIdsFilter(default_value='-')
    celery_parent_id.reset(celery_parent_id_token)
    celery_current_id.reset(celery_current_id_token)

    assert not hasattr(log_record, 'celery_parent_id')
    assert not hasattr(log_record, 'celery_current_id')
    filter_.filter(log_record)
    assert log_record.celery_parent_id == '-'
    assert log_record.celery_current_id == '-'


@pytest.mark.parametrize(
    ('uuid_length', 'expected'),
    [
        (6, 6),
        (16, 16),
        (None, 36),
        (38, 36),
    ],
)
def test_celery_filter_truncates_current_id_correctly(cid: str, log_record: LogRecord, uuid_length, expected):
    """
    If uuid is unspecified, the default should be 36.

    Otherwise, the id should be truncated to the specified length.
    """
    filter_ = CeleryTracingIdsFilter(uuid_length=uuid_length)
    celery_id = str(uuid4())
    celery_current_id.set(celery_id)

    assert not hasattr(log_record, 'celery_current_id')
    filter_.filter(log_record)
    assert log_record.celery_current_id == celery_id[:expected]


def test_celery_filter_maintains_current_behavior(cid: str, log_record: LogRecord):
    """Maintain default behavior with signature change

    Since the default values of CeleryTracingIdsFilter are being changed,
    the new default values should also not trim a hex uuid.
    """
    celery_id = uuid4().hex
    celery_current_id.set(celery_id)
    new_filter = CeleryTracingIdsFilter()

    assert not hasattr(log_record, 'celery_current_id')
    new_filter.filter(log_record)
    assert log_record.celery_current_id == celery_id
    new_filter_record_id = log_record.celery_current_id

    del log_record.celery_current_id

    original_filter = CeleryTracingIdsFilter(uuid_length=32)
    assert not hasattr(log_record, 'celery_current_id')
    original_filter.filter(log_record)
    assert log_record.celery_current_id == celery_id
    original_filter_record_id = log_record.celery_current_id

    assert original_filter_record_id == new_filter_record_id
