from uuid import UUID

import httpx
import pytest
from delorean import Delorean
from starlette import status

from framework.logging import debug
from main.custom_types import AssignmentT
from main.custom_types import ProjectT
from main.custom_types import UserT

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.functional,
]


async def create_user(client, *, name: str, is_admin: bool = False) -> UserT:
    user = UserT(name=name, is_admin=is_admin)
    resp = await client.post("/users/new/", content=user.json())
    assert resp.status_code == status.HTTP_201_CREATED

    payload = resp.json()
    debug(payload)
    assert not payload.get("errors")

    data = payload.get("data")
    assert data

    user_id = data.get("id")
    assert user_id

    user.id = user_id
    debug(user)

    return user


async def test_happy_path(asgi_client: httpx.AsyncClient, admin: UserT):
    resp: httpx.Response = await asgi_client.get("/users")
    assert resp.status_code == status.HTTP_200_OK

    payload = resp.json()
    assert "errors" not in payload
    data = payload.get("data")
    assert len(data) == 1
    assert data[0]["id"] == str(admin.id)
    assert data[0]["name"] == str(admin.name)
    assert data[0]["is_admin"] == admin.is_admin
    assert "password" not in data[0]

    user = UserT(name="user", password="user")
    resp: httpx.Response = await asgi_client.post(
        "/users", content=user.json()
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    resp: httpx.Response = await asgi_client.post(
        "/users",
        content=user.json(),
        auth=(admin.name, admin.password),
    )
    assert resp.status_code == status.HTTP_201_CREATED

    payload = resp.json()
    assert "errors" not in payload
    data = payload.get("data")
    assert isinstance(data, dict)
    assert "id" in data
    user.id = UUID(data["id"])

    project = ProjectT(name="project")

    resp: httpx.Response = await asgi_client.post(
        "/projects", content=project.json()
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    resp: httpx.Response = await asgi_client.post(
        "/projects",
        content=project.json(),
        auth=(admin.name, admin.password),
    )
    assert resp.status_code == status.HTTP_201_CREATED

    payload = resp.json()
    assert "errors" not in payload
    data = payload.get("data")
    assert isinstance(data, dict)
    assert "id" in data
    project.id = UUID(data["id"])

    begins = Delorean().date
    assignment = AssignmentT(
        user_id=user.id, project_id=project.id, begins=begins
    )
    resp: httpx.Response = await asgi_client.put(
        "/assignments",
        content=assignment.json(),
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    resp: httpx.Response = await asgi_client.put(
        "/assignments",
        content=assignment.json(),
        auth=(admin.name, admin.password),
    )
    assert resp.status_code == status.HTTP_200_OK

    payload = resp.json()
    assert "errors" not in payload
    data = payload.get("data")
    assert isinstance(data, dict)
    got: AssignmentT = AssignmentT.parse_obj(data)
    assert got.project_id == assignment.project_id
    assert got.user_id == assignment.user_id
    assert got.begins == assignment.begins
    assert got.ends == assignment.ends
    assert got.user == user
    assert got.project == project


async def test_asgi_app(asgi_client: httpx.AsyncClient, admin: UserT):
    response: httpx.Response = await asgi_client.get(
        "/", auth=(admin.name, admin.password)
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["request"]["client"]["host"] == "127.0.0.1"
    assert payload["request"]["client"]["port"] in range(1, 65535)
    assert payload["request"]["headers"]["host"] == "asgi"
    assert payload["request"]["headers"]["user-agent"] == "python-httpx/0.18.2"


@pytest.mark.webapp
async def test_web_app(web_client: httpx.AsyncClient, admin: UserT):
    try:
        resp: httpx.Response = await web_client.get(
            "/", auth=(admin.name, admin.password)
        )
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
