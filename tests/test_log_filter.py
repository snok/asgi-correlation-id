from logging import INFO, LogRecord
from uuid import uuid4

import pytest

from asgi_correlation_id import CorrelationIDFilter
from asgi_correlation_id.context import correlation_id


@pytest.fixture()
def cid():
    """Set and return a correlation ID"""
    cid = uuid4().hex
    correlation_id.set(cid)
    return cid


@pytest.fixture()
def log_record():
    """Create and return an INFO-level log record"""
    record = LogRecord(name='', level=INFO, pathname='', lineno=0, msg='Hello, world!', args=(), exc_info=None)
    return record


def test_filter_has_uuid_length_attributes():
    filter_ = CorrelationIDFilter(uuid_length=8)
    assert filter_.uuid_length == 8


def test_filter_adds_correlation_id(cid, log_record):
    filter_ = CorrelationIDFilter()

    assert not hasattr(log_record, 'correlation_id')
    filter_.filter(log_record)
    assert log_record.correlation_id == cid


def test_filter_truncates_correlation_id(cid, log_record):
    filter_ = CorrelationIDFilter(uuid_length=8)

    assert not hasattr(log_record, 'correlation_id')
    filter_.filter(log_record)
    assert len(log_record.correlation_id) == 8  # Needs to match uuid_length
    assert cid.startswith(log_record.correlation_id)  # And needs to be the first 8 characters of the id
