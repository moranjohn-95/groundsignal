from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from .planning_application import PlanningApplication

__all__ = ["Base", "PlanningApplication"]
