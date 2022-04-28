from logging import Filter
from typing import TYPE_CHECKING, Optional

from asgi_correlation_id.context import celery_current_id, celery_parent_id, correlation_id

if TYPE_CHECKING:
    from logging import LogRecord


# Middleware


class CorrelationIdFilter(Filter):
    """Logging filter to attached correlation IDs to log records"""

    def __init__(self, name: str = '', uuid_length: Optional[int] = None):
        super().__init__(name=name)
        self.uuid_length = uuid_length

    def filter(self, record: 'LogRecord') -> bool:
        """
        Attach a correlation ID to the log record.

        Since the correlation ID is defined in the middleware layer, any
        log generated from a request after this point can easily be searched
        for, if the correlation ID is added to the message, or included as
        metadata.
        """
        cid = correlation_id.get()
        if self.uuid_length is not None and cid:
            record.correlation_id = cid[: self.uuid_length]  # type: ignore[attr-defined]
        else:
            record.correlation_id = cid  # type: ignore[attr-defined]
        return True


# Celery extension


class CeleryTracingIdsFilter(Filter):
    def __init__(self, name: str = '', uuid_length: int = 32):
        super().__init__(name=name)
        self.uuid_length = uuid_length

    def filter(self, record: 'LogRecord') -> bool:
        """
        Append a parent- and current ID to the log record.

        The celery current ID is a unique ID generated for each new worker process.
        The celery parent ID is the current ID of the worker process that spawned
        the current process. If the worker process was spawned by a beat process
        or from an endpoint, the parent ID will be None.
        """
        pid = celery_parent_id.get()
        record.celery_parent_id = pid[: self.uuid_length] if pid else pid  # type: ignore[attr-defined]
        cid = celery_current_id.get()
        record.celery_current_id = cid[: self.uuid_length] if cid else cid  # type: ignore[attr-defined]
        return True
