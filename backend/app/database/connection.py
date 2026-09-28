from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# create_async_engine is lazy — it does not open connections at import time.
engine = create_async_engine(
    settings.database_url,
    # Pool sizing: keep it small for a single-process dev/assessment setup.
    pool_size=5,
    max_overflow=10,
    # Echo SQL only in debug mode to avoid log noise in production.
    echo=settings.app_debug,
)

# async_sessionmaker is the async equivalent of sessionmaker.
# expire_on_commit=False avoids implicit lazy-loads after commit inside an
# async context, where the session may already be closed.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request."""
    async with AsyncSessionLocal() as session:
        yield session
