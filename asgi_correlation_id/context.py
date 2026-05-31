from contextvars import ContextVar

# Middleware
correlation_id: ContextVar[str | None] = ContextVar('correlation_id', default=None)

# Celery extension
celery_parent_id: ContextVar[str | None] = ContextVar('celery_parent', default=None)
celery_current_id: ContextVar[str | None] = ContextVar('celery_current', default=None)
