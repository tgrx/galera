import secrets
from uuid import UUID

from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.security import HTTPBasic
from fastapi.security import HTTPBasicCredentials
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from framework.logging import debug
from framework.logging import logger
from main import db
from main.custom_types import AssignmentT
from main.custom_types import ProjectT
from main.custom_types import UserT

application = FastAPI()
security = HTTPBasic()


def raise_401():
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect credentials",
        headers={"WWW-Authenticate": "Basic"},
    )


def raise_403():
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden",
        headers={"WWW-Authenticate": "Basic"},
    )


async def get_current_user(
    credentials: HTTPBasicCredentials = Depends(security),
) -> UserT:
    try:
        obj = await db.get_user(name=credentials.username)
    except db.UserNotFoundError:
        raise_401()

    correct_username = secrets.compare_digest(
        credentials.username,
        obj.name,
    )
    correct_password = secrets.compare_digest(
        credentials.password,
        obj.password,
    )

    if not all((correct_username, correct_password)):
        raise_401()

    if not obj.is_admin:
        raise_403()

    user = UserT.from_orm(obj)

    return user


@application.get("/")
async def handler(request: Request, user=Depends(get_current_user)):
    debug(request)

    return {
        "request": {
            "client": {
                "host": request.client.host,
                "port": request.client.port,
            },
            "headers": request.headers,
            "user": user,
        }
    }


@application.get("/users")
async def handler():
    objs = await db.list_users()
    return {
        "data": [
            UserT.from_orm(obj).copy(exclude={"password"}) for obj in objs
        ]
    }


@application.get("/users/{user_id}")
async def handler(user_id: UUID, response: Response):
    try:
        obj = await db.get_user(user_id=user_id)
        user = UserT.from_orm(obj).copy(exclude={"password"})
        return {"data": user}
    except db.UserNotFoundError:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"errors": ["user not found"]}


@application.post("/users", status_code=status.HTTP_201_CREATED)
async def handler(user: UserT, admin=Depends(get_current_user)):
    logger.info(f"{admin = }")
    try:
        obj = await db.create_user(
            name=user.name, password=user.password, is_admin=user.is_admin
        )
        user.id = obj.id
        return {"data": user}
    except db.UserAlreadyExistsError:
        return {"errors": ["user already exists"]}


@application.get("/projects")
async def handler():
    objs = await db.list_projects()
    debug(objs)
    return {"data": [ProjectT.from_orm(obj) for obj in objs]}


@application.get("/projects/{project_id}")
async def handler(project_id: UUID, response: Response):
    try:
        obj = await db.get_project(project_id=project_id)
        user = ProjectT.from_orm(obj)
        return {"data": user}
    except db.ProjectNotFoundError:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"errors": ["project not found"]}


@application.post("/projects", status_code=status.HTTP_201_CREATED)
async def handler(project: ProjectT, admin=Depends(get_current_user)):
    logger.info(f"{admin = }")
    try:
        obj = await db.create_project(name=project.name)
        project.id = obj.id
        return {"data": project}
    except db.ProjectAlreadyExistsError:
        return {"errors": ["project already exists"]}


@application.get("/assignments")
async def handler():
    objs = await db.list_assignments()
    assignments = [AssignmentT.from_orm(obj) for obj in objs]
    return {"data": assignments}


@application.put("/assignments")
async def handler(assignment: AssignmentT, admin=Depends(get_current_user)):
    logger.info(f"{admin = }")
    try:
        obj = await db.upsert_assignment(
            begins=assignment.begins,
            ends=assignment.ends,
            project_id=assignment.project_id,
            user_id=assignment.user_id,
        )
        assignment: AssignmentT = AssignmentT.from_orm(obj)
        return {"data": assignment}
    except db.BadAssignmentError as err:
        return {"errors": [str(err)]}


if __name__ == "__main__":
    import uvicorn

    logger.info("running standalone webapp using uvicorn")
    uvicorn.run(application, host="0.0.0.0", port=8000, log_level="debug")
