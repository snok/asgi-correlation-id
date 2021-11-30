import logging
from uuid import UUID, uuid4

import pytest
from fastapi import Response
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

from tests.conftest import app

logger = logging.getLogger('asgi_correlation_id')

pytestmark = pytest.mark.asyncio


@app.get('/test', status_code=200)
async def test_view() -> dict:
    logger.debug('Test view')
    return {'test': 'test'}


@app.websocket_route('/ws')
async def websocket(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({'msg': 'Hello WebSocket'})
    await websocket.close()


valid_uuids = [
    [uuid4().hex, uuid4().hex],
    [str(uuid4()), str(uuid4())],
]


@pytest.mark.parametrize('values', valid_uuids)
async def test_returned_response_headers(client, values):
    """
    We expect:
     - our request id header to be returned back to us
     - the request id header name to be returned in access-control-expose-headers
    """
    # Check we get the right headers back
    correlation_id = values[0]
    response = await client.get('test', headers={'X-Request-ID': correlation_id})
    assert response.headers['access-control-expose-headers'] == 'X-Request-ID'
    assert UUID(response.headers['X-Request-ID']) == UUID(correlation_id)

    # And do it one more time, jic
    second_correlation_id = values[1]
    second_response = await client.get('test', headers={'X-Request-ID': second_correlation_id})
    assert second_response.headers['access-control-expose-headers'] == 'X-Request-ID'
    assert UUID(second_response.headers['X-Request-ID']) == UUID(second_correlation_id)

    # Then try without specifying a request id
    third_response = await client.get('test')
    assert third_response.headers['access-control-expose-headers'] == 'X-Request-ID'
    assert UUID(third_response.headers['X-Request-ID']) not in [UUID(correlation_id), UUID(second_correlation_id)]


bad_uuids = [
    'test',
    'bad-uuid',
    '1x' * 16,  # len of uuid is 32
    uuid4().hex[:-1] + 'x',
]


@pytest.mark.parametrize('value', bad_uuids)
async def test_non_uuid_header(client, caplog, value):
    """
    We expect the middleware to ignore our request ID and log a warning
    when the request ID we pass doesn't correspond to the uuid4 format.
    """
    response = await client.get('test', headers={'X-Request-ID': value})
    assert response.headers['X-Request-ID'] != value
    assert caplog.messages[0] == f"Generating new UUID, since header value '{value}' is invalid"


async def test_websocket_request(caplog):
    """
    We expect websocket requests to not be handled.

    This test could use improvement.
    """
    client = TestClient(app)
    with client.websocket_connect('/ws') as websocket:
        websocket.receive_json()
        assert caplog.messages == []


@app.get('/access-control-expose-headers')
async def access_control_view() -> dict:
    return Response(status_code=204, headers={'Access-Control-Expose-Headers': 'test1, test2'})


async def test_access_control_expose_headers(client, caplog):
    """
    The middleware should add the correlation ID header name to exposed headers.

    The middleware should not overwrite other values, but should append to it.
    """
    response = await client.get('access-control-expose-headers')
    assert response.headers['Access-Control-Expose-Headers'] == 'test1, test2, X-Request-ID'
