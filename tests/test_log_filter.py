import contextvars
from logging import INFO, LogRecord
from uuid import uuid4

import pytest

from asgi_correlation_id import CorrelationIdFilter
from asgi_correlation_id.context import correlation_id

# Initialize context variable to obtain a reset token which we can later use
# when testing application of filter default values.
correlation_id_token: contextvars.Token = correlation_id.set(None)


@pytest.fixture
def cid():
    """Set and return a correlation ID"""
    cid = uuid4().hex
    correlation_id.set(cid)
    return cid


@pytest.fixture
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
