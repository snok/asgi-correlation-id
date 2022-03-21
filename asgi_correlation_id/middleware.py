import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from starlette.datastructures import Headers

from asgi_correlation_id.context import correlation_id
from asgi_correlation_id.extensions.sentry import get_sentry_extension

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

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
            if message['type'] == 'http.response.start':
                raw_headers = [(k.decode(), v.decode()) for (k, v) in message['headers']]

                # add the non-null correlation_id
                correlation_id_local = correlation_id.get()
                if correlation_id_local:
                    raw_headers.append((self.header_name.encode('latin-1'), correlation_id_local.encode('latin-1')))
                    raw_headers.append((b'Access-Control-Expose-Headers', self.header_name.encode('latin-1')))

                response_headers = Headers(raw=raw_headers)
                message['headers'] = response_headers.raw

            await send(message)

        await self.app(scope, receive, handle_outgoing_request)
        return

    def __post_init__(self) -> None:
        """
        Load extensions on initialization.

        If Sentry is installed, propagate correlation IDs to Sentry events.
        If Celery is installed, propagate correlation IDs to spawned worker processes.
        """
        self.sentry_extension = get_sentry_extension()
        try:
            import celery  # noqa: F401, TC002

            from asgi_correlation_id.extensions.celery import load_correlation_ids

            load_correlation_ids()
        except ImportError:  # pragma: no cover
            pass
