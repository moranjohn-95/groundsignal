from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from .planning_application import PlanningApplication
from .user import User

__all__ = ["Base", "PlanningApplication", "User"]
