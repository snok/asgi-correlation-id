from unittest.mock import Mock
from uuid import uuid4

from asgi_correlation_id import correlation_id_filter
from asgi_correlation_id.context import correlation_id


def test_correlation_id_filter():
    mock_record = Mock()

    cid = uuid4().hex
    correlation_id.set(cid)

    # Call with no uuid length
    correlation_id_filter(None)().filter(mock_record)
    assert mock_record.correlation_id == cid

    # Call with uuid length
    for length in [0, 14, 30, 100]:
        correlation_id_filter(uuid_length=length)().filter(mock_record)
        assert mock_record.correlation_id == cid[:length]
