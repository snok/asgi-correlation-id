from logging import Filter, LogRecord
from typing import Type

from asgi_correlation_id.context import celery_current_id, celery_parent_id
from asgi_correlation_id.middleware import correlation_id


def correlation_id_filter(uuid_length: int = 32) -> Type[Filter]:
    class CorrelationId(Filter):
        def filter(self, record: LogRecord) -> bool:
            """
            Attach a correlation ID to the log record.

            Added properties are available as any other LogRecord attribute.

            As long as a project's log formatter is set up to include the correlation_id
            attribute, any log belonging to that single request will contain the same ID.
            """
            cid = correlation_id.get()
            record.correlation_id = cid[:uuid_length] if cid else cid  # type: ignore[attr-defined]
            return True

    return CorrelationId


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
