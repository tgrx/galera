from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field


class OrmModel(BaseModel):
    class Config:
        orm_mode = True


class Entity(OrmModel):
    id: Optional[UUID] = Field(default=None)


class UserT(Entity):
    name: str = Field(...)
    password: Optional[str] = Field(default=None)
    is_admin: bool = Field(default=False)


class ProjectT(Entity):
    name: str = Field(...)


class AssignmentT(OrmModel):
    user: Optional[UserT] = Field(default=None)
    project: Optional[ProjectT] = Field(default=None)
    user_id: UUID = Field(...)
    project_id: UUID = Field(...)
    begins: date = Field(...)
    ends: Optional[date] = Field(default=None)
