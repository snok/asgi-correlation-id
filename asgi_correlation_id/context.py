from contextvars import ContextVar

correlation_id: ContextVar[str | None] = ContextVar('correlation_id', default=None)
