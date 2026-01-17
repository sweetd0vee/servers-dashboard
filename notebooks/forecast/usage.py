from forecaster import ProphetForecaster

from src.app.connection import SessionLocal
from src.app.facts_crud import DBCRUD

forecaster = ProphetForecaster()
result = forecaster.generate_forecast(SessionLocal, DBCRUD, "DataLake-DBN1", "cpu_usage_average")