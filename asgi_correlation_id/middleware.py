import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from asgi_correlation_id.context import correlation_id
from asgi_correlation_id.extensions.celery import load_celery_extension
from asgi_correlation_id.extensions.sentry import get_sentry_extension

logger = logging.getLogger('asgi_correlation_id')


def is_valid_uuid(uuid_: str) -> bool:
    """
    Check whether a string is a valid v4 uuid.
    """
    try:
        return bool(UUID(uuid_, version=4))
    except ValueError:
        return False


@dataclass()
class CorrelationIdMiddleware:
    app: ASGIApp
    header_name: str = 'X-Request-ID'
    validate_header_as_uuid: bool = True

    def __post_init__(self) -> None:
        """
        Load extensions on initialization.

        If Sentry is installed, propagate correlation IDs to Sentry events.
        If Celery is installed, propagate correlation IDs to spawned worker processes.
        """
        self.sentry_extension = get_sentry_extension()
        load_celery_extension()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

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

        async def handle_outgoing_request(message: Message) -> None:
            if message['type'] == 'http.response.start':
                headers = {k.decode(): v.decode() for (k, v) in message['headers']}
                headers[self.header_name] = correlation_id.get()
                headers['Access-Control-Expose-Headers'] = self.header_name
                response_headers = Headers(headers=headers)
                message['headers'] = response_headers.raw

            await send(message)

        return await self.app(scope, receive, handle_outgoing_request)
