import httpx
import pytest

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.functional,
]


async def test_asgi_app(asgi_client: httpx.AsyncClient):
    response: httpx.Response = await asgi_client.get("/")
    assert response.status_code == 200

    payload = response.json()
    assert payload["request"]["client"]["host"] == "127.0.0.1"
    assert payload["request"]["client"]["port"] in range(1, 65535)
    assert payload["request"]["headers"]["host"] == "asgi"
    assert payload["request"]["headers"]["user-agent"] == "python-httpx/0.18.2"


@pytest.mark.webapp
async def test_web_app(web_client: httpx.AsyncClient):
    try:
        resp: httpx.Response = await web_client.get("/")
        assert resp.status_code == 200

        payload = resp.json()
        assert payload["request"]["client"]["host"] == "127.0.0.1"
        assert payload["request"]["client"]["port"] in range(1, 65535)
        assert payload["request"]["headers"]["host"] == "localhost:8000"
        assert (
            payload["request"]["headers"]["user-agent"]
            == "python-httpx/0.18.2"
        )

    except (httpx.ConnectError, httpx.TimeoutException) as err:
        raise AssertionError(
            f"unable to connect to server @ {web_client.base_url}"
        ) from err
