from logging import Filter, LogRecord
from typing import Optional, Type

from asgi_correlation_id.context import celery_current_id, celery_parent_id, correlation_id

# Middleware


def correlation_id_filter(uuid_length: Optional[int] = None) -> Type[Filter]:
    class CorrelationId(Filter):
        def filter(self, record: LogRecord) -> bool:
            """
            Attach a correlation ID to the log record.

            Since the correlation ID is defined in the middleware layer, any
            log generated from a request after this point can easily be searched
            for, if the correlation ID is added to the message, or included as
            metadata.
            """
            cid = correlation_id.get()
            if uuid_length is not None and cid:
                record.correlation_id = cid[:uuid_length]  # type: ignore[attr-defined]
            else:
                record.correlation_id = cid  # type: ignore[attr-defined]
            return True

    return CorrelationId


# Celery extension


def celery_tracing_id_filter(uuid_length: int = 32) -> Type[Filter]:
    class CeleryTracingIds(Filter):
        def filter(self, record: LogRecord) -> bool:
            """
            Append a parent- and current ID to the log record.

            The celery current ID is a unique ID generated for each new worker process.
            The celery parent ID is the current ID of the worker process that spawned
            the current process. If the worker process was spawned by a beat process
            or from an endpoint, the parent ID will be None.
            """
            pid = celery_parent_id.get()
            record.celery_parent_id = pid[:uuid_length] if pid else pid  # type: ignore[attr-defined]
            cid = celery_current_id.get()
            record.celery_current_id = cid[:uuid_length] if cid else cid  # type: ignore[attr-defined]
            return True

    return CeleryTracingIds
