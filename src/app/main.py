from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import asyncio
from typing import List, Optional

from connection import get_db, engine
import models as db_models
# from . import schemas as pydantic_models
# from .crud import DBCRUD
# from prophet_service import ProphetForecaster
# from anomaly_detector import AnomalyDetector
from endpoints import router as api_router
from base_logger import logger

# Создание таблиц
db_models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AIOps Dashboard API",
    description="API для мониторинга и прогнозирования нагрузки серверов",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене заменить на конкретные домены
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальные сервисы
# forecaster = ProphetForecaster()
# anomaly_detector = AnomalyDetector()

# Подключение роутеров
app.include_router(api_router, prefix="/api/v1")


# @app.on_event("startup")
# async def startup_event():
#     """Запуск фоновых задач при старте"""
#     logger.info("AIOps Dashboard API starting up...")
#
#
# @app.on_event("shutdown")
# async def shutdown_event():
#     """Очистка при завершении"""
#     logger.info("AIOps Dashboard API shutting down...")


# @app.get("/", include_in_schema=False)
# async def root():
#     return {
#         "message": "AIOps Dashboard API",
#         "version": "1.0.0",
#         "docs": "/docs",
#         "redoc": "/redoc"
#     }