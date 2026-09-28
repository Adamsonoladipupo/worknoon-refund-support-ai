import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.database.base import Base

# Import all models so their tables are registered on Base.metadata
# and picked up by autogenerate. Add new models here as they are created.
import app.models.customer  # noqa: F401
import app.models.order  # noqa: F401
import app.models.order_item  # noqa: F401
import app.models.refund_request  # noqa: F401

# Alembic Config gives access to the .ini values.
config = context.config

# Set up Python logging from the ini file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is the metadata object autogenerate will inspect.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without an active DB connection (produces a SQL script)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Emit a precise BIGINT / UUID comparison instead of the generic one.
        # and Detect database column type changes during autogeneration.
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations using an async connection."""
    # Create a throw-away engine just for migration runs; this is separate
    # from the application engine so pooling settings don't interfere.
    connectable = create_async_engine(settings.database_url, echo=False)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
