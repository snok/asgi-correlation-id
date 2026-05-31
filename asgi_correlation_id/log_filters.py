from logging import Filter, LogRecord

from asgi_correlation_id.context import correlation_id


def _trim_string(string: str | None, string_length: int | None) -> str | None:
    return string[:string_length] if string_length is not None and string else string


class CorrelationIdFilter(Filter):
    """Logging filter to attached correlation IDs to log records"""

    def __init__(self, name: str = '', uuid_length: int | None = None, default_value: str | None = None):
        super().__init__(name=name)
        self.uuid_length = uuid_length
        self.default_value = default_value

    def filter(self, record: LogRecord) -> bool:
        """
        Attach a correlation ID to the log record.

        Since the correlation ID is defined in the middleware layer, any
        log generated from a request after this point can easily be searched
        for, if the correlation ID is added to the message, or included as
        metadata.
        """
        cid = correlation_id.get(self.default_value)
        record.correlation_id = _trim_string(cid, self.uuid_length)
        return True
