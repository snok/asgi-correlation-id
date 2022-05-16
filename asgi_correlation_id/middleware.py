import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional
from uuid import UUID, uuid4

from starlette.datastructures import Headers, MutableHeaders

from asgi_correlation_id.context import correlation_id
from asgi_correlation_id.extensions.sentry import get_sentry_extension

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger('asgi_correlation_id')


def is_valid_uuid4(uuid_: str) -> bool:
    """
    Check whether a string is a valid v4 uuid.
    """
    try:
        return bool(UUID(uuid_, version=4))
    except ValueError:
        return False


FAILED_VALIDATION_MESSAGE = 'Generated new request ID (%s), since request header value failed validation'


@dataclass
class CorrelationIdMiddleware:
    app: 'ASGIApp'
    header_name: str = 'X-Request-ID'

    # ID-generating callable
    generator: Callable[[], str] = field(default=lambda: uuid4().hex)

    # ID validator
    validator: Optional[Callable[[str], bool]] = field(default=is_valid_uuid4)

    # ID transformer - can be used to clean/mutate IDs
    transformer: Optional[Callable[[str], str]] = field(default=lambda a: a)

    async def __call__(self, scope: 'Scope', receive: 'Receive', send: 'Send') -> None:
        """
        Load request ID from headers if present. Generate one otherwise.
        """
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        # Try to load request ID from the request headers
        header_value = Headers(scope=scope).get(self.header_name.lower())

        if not header_value:
            # Generate request ID if none was found
            id_value = self.generator()
        elif self.validator and not self.validator(header_value):
            # Also generate a request ID if one was found, but it was deemed invalid
            id_value = self.generator()
            logger.warning(FAILED_VALIDATION_MESSAGE, header_value)
        else:
            # Otherwise, use the found request ID
            id_value = header_value

        # Clean/change the ID if needed
        if self.transformer:
            id_value = self.transformer(id_value)

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
        self.sentry_extension = get_sentry_extension()
        try:
            import celery  # noqa: F401, TC002

            from asgi_correlation_id.extensions.celery import load_correlation_ids

            load_correlation_ids()
        except ImportError:  # pragma: no cover
            pass
