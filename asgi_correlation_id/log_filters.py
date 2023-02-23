from logging import Filter
from typing import TYPE_CHECKING, Optional

from asgi_correlation_id.context import correlation_id

if TYPE_CHECKING:
    from logging import LogRecord


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
        record.correlation_id = cid[: self.uuid_length] if self.uuid_length is not None and cid else cid
        return True
