import logging
from dataclasses import dataclass, field
from typing import Callable, List
from uuid import uuid4

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from asgi_correlation_id.context import correlation_id
from asgi_correlation_id.extensions.sentry import get_sentry_extension
from asgi_correlation_id.validators import is_valid_uuid

logger = logging.getLogger('asgi_correlation_id')


@dataclass
class CorrelationIdMiddleware:
    app: ASGIApp
    header_name: str = 'X-Request-ID'

    # ID generating function
    generator: Callable[[], str] = field(default=lambda: uuid4().hex)

    # Validators for discarding badly formatted IDs
    validators: List[Callable[[str], bool]] = None  # type: ignore[assignment]

    # Extra handler layer for mutating IDs if needed
    transformer: Callable[[str], str] = field(default=lambda a: a)

    # Deprecated and will be removed in v2, use validators instead
    validate_header_as_uuid: bool = True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Load request ID from headers if present. Generate one otherwise.
        """
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        header_value: str = Headers(scope=scope).get(self.header_name.lower())

        if not header_value:
            id_value: str = self.transformer(self.generator())
        elif self.validators and not all(validator(header_value) for validator in self.validators):
            logger.warning("Generating new ID, since header value '%s' is invalid", header_value)
            id_value = self.transformer(self.generator())
        else:
            id_value = self.transformer(header_value)

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

        await self.app(scope, receive, handle_outgoing_request)
        return

    def __post_init__(self) -> None:
        """
        Load extensions on initialization.

        If Sentry is installed, propagate correlation IDs to Sentry events.
        If Celery is installed, propagate correlation IDs to spawned worker processes.
        """
        if self.validators is None:
            self.validators = [is_valid_uuid] if self.validate_header_as_uuid else []

        self.sentry_extension = get_sentry_extension()
        try:
            import celery  # noqa: F401

            from asgi_correlation_id.extensions.celery import load_correlation_ids

            load_correlation_ids()
        except ImportError:  # pragma: no cover
            pass
