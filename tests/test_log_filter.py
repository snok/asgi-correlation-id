from logging import INFO, LogRecord
from uuid import uuid4

import pytest

from asgi_correlation_id import CeleryTracingIdsFilter, CorrelationIdFilter
from asgi_correlation_id.context import celery_current_id, celery_parent_id, correlation_id


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
    filter_ = CorrelationIdFilter(uuid_length=8)
    assert filter_.uuid_length == 8


def test_filter_adds_correlation_id(cid, log_record):
    filter_ = CorrelationIdFilter()

    assert not hasattr(log_record, 'correlation_id')
    filter_.filter(log_record)
    assert log_record.correlation_id == cid


def test_filter_truncates_correlation_id(cid, log_record):
    filter_ = CorrelationIdFilter(uuid_length=8)

    assert not hasattr(log_record, 'correlation_id')
    filter_.filter(log_record)
    assert len(log_record.correlation_id) == 8  # Needs to match uuid_length
    assert cid.startswith(log_record.correlation_id)  # And needs to be the first 8 characters of the id


def test_celery_filter_has_uuid_length_attributes():
    filter_ = CeleryTracingIdsFilter(uuid_length=8)
    assert filter_.uuid_length == 8


def test_celery_filter_adds_parent_id(cid, log_record):
    filter_ = CeleryTracingIdsFilter()
    celery_parent_id.set('a')

    assert not hasattr(log_record, 'celery_parent_id')
    filter_.filter(log_record)
    assert log_record.celery_parent_id == 'a'


def test_celery_filter_adds_current_id(cid, log_record):
    filter_ = CeleryTracingIdsFilter()
    celery_current_id.set('b')

    assert not hasattr(log_record, 'celery_current_id')
    filter_.filter(log_record)
    assert log_record.celery_current_id == 'b'


def test_celery_filter_does_not_truncate_current_id(cid, log_record):
    filter_ = CeleryTracingIdsFilter()
    celery_id: str = str(uuid4())
    celery_current_id.set(celery_id)

    assert not hasattr(log_record, 'celery_current_id')
    filter_.filter(log_record)
    assert log_record.celery_current_id == celery_id


def test_celery_filter_maintains_current_behavior(cid, log_record):
    """Maintain default behavior with signature change

    Since the default values of CeleryTracingIdsFilter are being changed,
    the new default values should also not trim a hex uuid.
    """
    celery_id: str = uuid4().hex
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


def test_celery_filter_does_truncates_current_id(cid, log_record):
    filter_ = CeleryTracingIdsFilter(uuid_length=16)
    celery_id: str = uuid4().hex
    celery_current_id.set(celery_id)

    assert not hasattr(log_record, 'celery_current_id')
    filter_.filter(log_record)
    assert log_record.celery_current_id == celery_id[:16]
