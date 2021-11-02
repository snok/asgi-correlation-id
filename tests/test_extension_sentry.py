from unittest.mock import Mock

import sentry_sdk

from asgi_correlation_id.extensions.sentry import set_transaction_id

id_value = 'test'


def test_sentry_sdk_installed(mocker):
    """
    Check that the scope.set_tag method is called when Sentry is installed.
    """
    set_tag_mock = Mock()
    scope_mock = Mock()
    scope_mock.set_tag = set_tag_mock

    class MockedScope:
        def __enter__(self):
            return scope_mock

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    mocker.patch.object(sentry_sdk, 'configure_scope', return_value=MockedScope())
    set_transaction_id(id_value)
    set_tag_mock.assert_called_once_with('transaction_id', id_value)
