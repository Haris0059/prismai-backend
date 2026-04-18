from sqlalchemy.ext.asyncio import create_async_engine
from app.core.settings import settings

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"prepared_statement_cache_size": 0},
)
