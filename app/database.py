
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# engine = create_async_engine(DATABASE_URL, echo=True)
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_size=20,       # Number of connections to keep in the pool
    max_overflow=30, 
)

async_session = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with async_session() as session:
        yield session
