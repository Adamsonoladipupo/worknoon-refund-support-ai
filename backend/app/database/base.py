from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy models.

    All model classes must inherit from this Base so that Alembic's
    autogenerate can discover them via Base.metadata.
    """

    pass
