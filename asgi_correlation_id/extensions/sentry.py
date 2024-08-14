from typing import Callable


def get_sentry_extension() -> Callable[[str], None]:
    """
    Return set_transaction_id, if the Sentry-sdk is installed.
    """
    try:
        import sentry_sdk  # noqa: F401, TC002

        from asgi_correlation_id.extensions.sentry import set_transaction_id

        return set_transaction_id
    except ImportError:  # pragma: no cover
        return lambda correlation_id: None


def set_transaction_id(correlation_id: str) -> None:
    """
    Set Sentry's event transaction ID as the current correlation ID.

    The transaction ID is displayed in a Sentry event's detail view,
    which makes it easier to correlate logs to specific events.
    """
    import sentry_sdk
    from packaging import version

    if version.parse(sentry_sdk.VERSION) >= version.parse('2.12.0'):
        scope = sentry_sdk.get_isolation_scope()
        scope.set_tag('transaction_id', correlation_id)
    else:
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag('transaction_id', correlation_id)
