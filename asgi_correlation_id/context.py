from contextvars import ContextVar
from typing import Optional

# Middleware
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)

# Celery extension
celery_parent_id: ContextVar[Optional[str]] = ContextVar('celery_parent', default=None)
celery_current_id: ContextVar[Optional[str]] = ContextVar('celery_current', default=None)
