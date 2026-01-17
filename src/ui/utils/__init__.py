# Import from data_loader (loads from database) with fallback to data_generator
try:
    from .data_loader import (generate_forecast, generate_server_data,
                              load_data_from_database)
except ImportError:
    # Fallback to data_generator if data_loader is not available
    from .data_generator import generate_forecast, generate_server_data
    load_data_from_database = None
from .alert_rules import AlertSeverity, ServerStatus, alert_system
