import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping, Optional, Tuple, Type, Union
from uuid import UUID, uuid4

from starlette.datastructures import Headers, MutableHeaders

from asgi_correlation_id.context import correlation_id
from asgi_correlation_id.extensions.sentry import get_sentry_extension

if TYPE_CHECKING:
    from types import TracebackType

    from starlette.types import ASGIApp, Message, Receive, Scope, Send

ExcInfoType = Union[Tuple[Type[BaseException], BaseException, 'TracebackType', None], Tuple[None, None, None], None]
ArgsType = Union[Tuple[Any], Mapping[str, Any], None]

logger = logging.getLogger('asgi_correlation_id')


def is_valid_uuid(uuid_: str) -> bool:
    """
    Check whether a string is a valid v4 uuid.
    """
    try:
        return bool(UUID(uuid_, version=4))
    except ValueError:
        return False


@dataclass
class CorrelationIdMiddleware:
    app: 'ASGIApp'
    header_name: str = 'X-Request-ID'
    validate_header_as_uuid: bool = True

    async def __call__(self, scope: 'Scope', receive: 'Receive', send: 'Send') -> None:
        """
        Load request ID from headers if present. Generate one otherwise.
        """
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        header_value = Headers(scope=scope).get(self.header_name.lower())

        if not header_value:
            id_value = uuid4().hex
        elif self.validate_header_as_uuid and not is_valid_uuid(header_value):
            logger.warning('Generating new UUID, since header value \'%s\' is invalid', header_value)
            id_value = uuid4().hex
        else:
            id_value = header_value

        correlation_id.set(id_value)
        self.sentry_extension(id_value)

        async def handle_outgoing_request(message: 'Message') -> None:
            if message['type'] == 'http.response.start' and correlation_id.get():
                headers = MutableHeaders(scope=message)
                headers.append(self.header_name, correlation_id.get())
                headers.append('Access-Control-Expose-Headers', self.header_name)

            await send(message)

        await self.app(scope, receive, handle_outgoing_request)
        return

    def __post_init__(self) -> None:
        """
        Load extensions on initialization.

        If Sentry is installed, propagate correlation IDs to Sentry events.
        If Celery is installed, propagate correlation IDs to spawned worker processes.
        """
        _set_log_record_factory()
        self.sentry_extension = get_sentry_extension()
        try:
            import celery  # noqa: F401, TC002

            from asgi_correlation_id.extensions.celery import load_correlation_ids

            load_correlation_ids()
        except ImportError:  # pragma: no cover
            pass


def _set_log_record_factory() -> None:
    """Set a custom log record factory which enriches log records with correlation IDs"""
    # TODO: prevent this from being called twice
    old_factory = logging.getLogRecordFactory()

    def new_factory(
        name: str,
        level: int,
        fn: str,
        lno: int,
        msg: Any,
        args: ArgsType,
        exc_info: ExcInfoType,
        func: Optional[str] = None,
        sinfo: Optional[str] = None,
        **kwargs: Any,
    ) -> logging.LogRecord:
        """Log record factory which adds `correlation_id` attribute"""
        record = old_factory(name, level, fn, lno, msg, args, exc_info, func=func, sinfo=sinfo, **kwargs)
        record.correlation_id = correlation_id.get()  # type: ignore[attr-defined]
        # TODO: if required set celery correlation IDs
        return record

    logger.debug('Setting %s log record factory', __package__)
    logging.setLogRecordFactory(new_factory)
