import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Expects something like postgresql+asyncpg://user:pass@host:5432/db
# We provide a default for local development using the docker-compose setup
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://agentshield:agentshield_password@localhost:5432/agentshield"
)

# SQL echo logs every statement (including action payloads) — keep it off unless
# explicitly enabled for local debugging via SQL_ECHO=true.
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() in ("1", "true", "yes")

engine = create_async_engine(DATABASE_URL, echo=SQL_ECHO)

async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with async_session() as session:
        yield session
