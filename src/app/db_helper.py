from functools import lru_cache
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def build_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "server_metrics")

    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(
        build_database_url(),
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False,
    )


@lru_cache(maxsize=1)
def get_session_local():
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
