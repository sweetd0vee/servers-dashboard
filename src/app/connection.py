from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
# from contextlib import contextmanager
import os
from dotenv import load_dotenv
from base_logger import logger

load_dotenv()

# Получаем параметры подключения из переменных окружения
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "server_metrics") # TODO переписать конфиг


# Создаем строку подключения
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
logger.info(f"DATABASE_URL: {DATABASE_URL}")

# Создаем движок SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Проверка соединения перед использованием
    pool_recycle=300,  # Переподключение каждые 300 секунд
    echo=False  # Установите True для отладки SQL запросов
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency для получения сессии БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# @contextmanager
# def get_db_session():
#     """
#     Контекстный менеджер для работы с сессией БД.
#     Автоматически обрабатывает commit и rollback.
#     """
#     session = SessionLocal()
#     try:
#         yield session
#         session.commit()
#     except Exception as e:
#         session.rollback()
#         logger.error(f"Ошибка в транзакции: {str(e)}")
#         raise
#     finally:
#         session.close()