from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.db.engine import engine

async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
