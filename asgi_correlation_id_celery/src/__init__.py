from contextvars import ContextVar
from logging import Filter, LogRecord
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional
from uuid import uuid4

from celery.signals import before_task_publish, task_postrun, task_prerun

if TYPE_CHECKING:
    from celery import Task

__all__ = (
    'CeleryTracingIdsFilter',
    'celery_current_id',
    'celery_parent_id',
)

celery_parent_id: ContextVar[Optional[str]] = ContextVar('celery_parent', default=None)
celery_current_id: ContextVar[Optional[str]] = ContextVar('celery_current', default=None)

uuid_hex_generator: Callable[[], str] = lambda: uuid4().hex


def load_correlation_ids(header_key: str = 'CORRELATION_ID', generator: Callable[[], str] = uuid_hex_generator) -> None:
    """
    Transfer correlation IDs from a HTTP request to a Celery worker,
    when spawned from a request.

    This is called as long as Celery is installed.
    """
    from asgi_correlation_id.context import correlation_id

    # Load sentry extension if it's present
    try:
        from asgi_correlation_id_sentry_extension import get_sentry_extension

        sentry_extension = get_sentry_extension()
    except ImportError:
        sentry_extension = lambda _: None  # noqa: E731

    @before_task_publish.connect(weak=False)
    def transfer_correlation_id(headers: Dict[str, str], **kwargs: Any) -> None:
        """
        Transfer correlation ID from request thread to Celery worker, by adding
        it as a header.

        This way we're able to correlate work executed by Celery workers, back
        to the originating request, when there was one.
        """
        cid = correlation_id.get()
        if cid:
            headers[header_key] = cid

    @task_prerun.connect(weak=False)
    def load_correlation_id(task: 'Task', **kwargs: Any) -> None:
        """
        Set correlation ID from header if it exists.

        If it doesn't exist, generate a unique ID for the task anyway.
        """
        id_value = task.request.get(header_key)
        if id_value:
            correlation_id.set(id_value)
            sentry_extension(id_value)
        else:
            generated_correlation_id = generator()
            correlation_id.set(generated_correlation_id)
            sentry_extension(generated_correlation_id)

    @task_postrun.connect(weak=False)
    def cleanup(**kwargs: Any) -> None:
        """
        Clear context vars, to avoid re-using values in the next task.

        Context vars are cleared automatically in a HTTP request-setting,
        but must be manually reset for workers.
        """
        correlation_id.set(None)


def load_celery_current_and_parent_ids(
    header_key: str = 'CELERY_PARENT_ID',
    generator: Callable[[], str] = uuid_hex_generator,
    use_internal_celery_task_id: bool = False,
) -> None:
    """
    Configure Celery event hooks for generating tracing IDs with depth.

    This is not called automatically by the middleware.
    To use this, users should manually run it during startup.
    """

    @before_task_publish.connect(weak=False)
    def publish_task_from_worker_or_request(headers: Dict[str, str], **kwargs: Any) -> None:
        """
        Transfer the current ID to the next Celery worker, by adding
        it as a header.

        This way we're able to tell which process spawned the next task.
        """
        current = celery_current_id.get()
        if current:
            headers[header_key] = current

    @task_prerun.connect(weak=False)
    def worker_prerun(task_id: str, task: 'Task', **kwargs: Any) -> None:
        """
        Set current ID, and parent ID if it exists.
        """
        parent_id = task.request.get(header_key)
        if parent_id:
            celery_parent_id.set(parent_id)

        celery_id = task_id if use_internal_celery_task_id else generator()
        celery_current_id.set(celery_id)

    @task_postrun.connect(weak=False)
    def clean_up(**kwargs: Any) -> None:
        """
        Clear context vars, to avoid re-using values in the next task.
        """
        celery_current_id.set(None)
        celery_parent_id.set(None)


class CeleryTracingIdsFilter(Filter):
    def __init__(self, name: str = '', uuid_length: Optional[int] = None):
        super().__init__(name=name)
        self.uuid_length = uuid_length

    def filter(self, record: LogRecord) -> bool:
        """
        Append a parent- and current ID to the log record.

        The celery current ID is a unique ID generated for each new worker process.
        The celery parent ID is the current ID of the worker process that spawned
        the current process. If the worker process was spawned by a beat process
        or from an endpoint, the parent ID will be None.
        """
        pid = celery_parent_id.get()
        record.celery_parent_id = pid[: self.uuid_length] if self.uuid_length is not None and pid else pid
        cid = celery_current_id.get()
        record.celery_current_id = cid[: self.uuid_length] if self.uuid_length is not None and cid else cid
        return True
