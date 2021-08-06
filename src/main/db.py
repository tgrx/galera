from contextlib import asynccontextmanager
from datetime import date
from typing import List
from typing import Optional
from uuid import uuid4

from delorean import Delorean
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import ForeignKey
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import and_
from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import contains_eager
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker

from framework.config import settings
from framework.logging import debug
from framework.logging import logger

_db_url = settings.DATABASE_URL.replace("postgres", "postgresql")

engine = create_async_engine(
    _db_url.replace("://", "+asyncpg://"),
    echo=settings.MODE_DEBUG_SQL,
)

engine_sync = create_engine(_db_url, echo=settings.MODE_DEBUG_SQL)

Session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    future=True,
)


@asynccontextmanager
async def begin_session():
    async with Session() as session:
        async with session.begin():
            yield session


Base = declarative_base()


class Model(Base):
    __abstract__ = True
    __mapper_args__ = {
        "eager_defaults": True,
    }

    id = Column(
        UUID(as_uuid=True),
        default=uuid4,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class User(Model):
    __tablename__ = "users"

    name = Column(
        Text,
        nullable=False,
        unique=True,
    )
    password = Column(
        Text,
        nullable=True,
    )
    is_admin = Column(
        Boolean,
        default=False,
        nullable=False,
        server_default="false",
    )


class Project(Model):
    __tablename__ = "projects"

    name = Column(
        Text,
        nullable=False,
        unique=True,
    )


class Assignment(Model):
    __tablename__ = "assignments"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            User.id,
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            Project.id,
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    begins = Column(
        Date,
        default=lambda: Delorean().date,
        nullable=False,
        server_default=text("current_date"),
    )
    ends = Column(
        Date,
        nullable=True,
    )

    user = relationship(
        User,
        foreign_keys=[user_id],
        uselist=False,
    )

    project = relationship(
        Project,
        foreign_keys=[project_id],
        uselist=False,
    )

    __table_args__ = (UniqueConstraint("project_id", "user_id"),)


def create_tables():
    Base.metadata.create_all(engine_sync)
    logger.info("tables are created")


class DbError(RuntimeError):
    pass


class UserAlreadyExistsError(DbError):
    pass


async def create_user(
    *,
    is_admin: bool = False,
    password: Optional[str] = None,
    name: str,
) -> User:
    try:
        async with begin_session() as session:
            user = User(
                is_admin=is_admin,
                name=name,
                password=password,
            )
            session.add(user)
        return user
    except IntegrityError as err:
        raise UserAlreadyExistsError from err


class UserNotFoundError(DbError):
    pass


async def get_user(
    *,
    user_id: Optional[UUID] = None,
    name: Optional[str] = None,
) -> User:
    if not bool(user_id) ^ bool(name):
        raise UserNotFoundError

    if name:
        c = and_(User.name == name)
    else:
        c = and_(User.id == user_id)

    q = select(User).where(c).limit(1)
    try:
        async with begin_session() as session:
            result = await session.execute(q)
            obj = result.scalars().one()
        return obj
    except NoResultFound as err:
        raise UserNotFoundError from err


async def list_users() -> List[User]:
    q = select(User)
    async with begin_session() as session:
        result = await session.execute(q)
        objs = result.scalars()
    return objs


class ProjectAlreadyExistsError(DbError):
    pass


async def create_project(
    *,
    name: str,
) -> Project:
    try:
        async with begin_session() as session:
            project = Project(name=name)
            session.add(project)
        return project
    except IntegrityError as err:
        raise ProjectAlreadyExistsError from err


class ProjectNotFoundError(DbError):
    pass


async def get_project(
    *,
    project_id: UUID,
) -> Project:
    q = select(Project).where(Project.id == project_id).limit(1)
    try:
        async with begin_session() as session:
            result = await session.execute(q)
            obj = result.scalars().one()
        return obj
    except NoResultFound as err:
        raise ProjectNotFoundError from err


async def list_projects() -> List[Project]:
    q = select(Project)
    async with begin_session() as session:
        result = await session.execute(q)
        objs = result.scalars()
    return objs


async def list_assignments():
    q = select(Assignment).options(
        joinedload(Assignment.project),
        joinedload(Assignment.user),
    )
    async with begin_session() as session:
        result = await session.execute(q)
    return result.scalars()


class BadAssignmentError(DbError):
    pass


async def upsert_assignment(
    *,
    project_id: UUID,
    user_id: UUID,
    begins: date,
    ends: Optional[date] = None,
):
    values = {
        Assignment.project_id: project_id,
        Assignment.user_id: user_id,
        Assignment.begins: begins,
        Assignment.ends: ends,
    }

    qi = (
        insert(Assignment)
        .values(values)
        .on_conflict_do_update(
            index_elements=[
                Assignment.project_id,
                Assignment.user_id,
            ],
            set_={
                Assignment.begins: begins,
                Assignment.ends: ends,
            },
        )
        .returning(
            Assignment.id,
        )
    )

    qsf = lambda _id: (
        select(Assignment)
        .where(Assignment.id == _id)
        .options(
            joinedload(Assignment.project),
            joinedload(Assignment.user),
        )
    )

    try:
        async with begin_session() as session:
            result = await session.execute(qi)
            assignment_id = result.scalar_one()

            qs = qsf(assignment_id)
            result = await session.execute(qs)
            assignment = result.scalars().one()
    except IntegrityError as err:
        raise BadAssignmentError("invalid project_id or user_id") from err

    return assignment


if __name__ == "__main__":
    create_tables()
