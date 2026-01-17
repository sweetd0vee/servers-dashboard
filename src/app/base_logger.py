import logging
import sys
from datetime import datetime
from pathlib import Path


# Создаем директорию для логов если ее нет
log_dir = Path(__file__).resolve().parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

# Формат даты для имени файла
current_date = datetime.now().strftime("%Y-%m-%d")
log_file = log_dir / f"servers_analysis_{current_date}.log"

# Создаем форматтер
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Создаем логгер
logger = logging.getLogger('server_analysis')
logger.setLevel(logging.INFO)

if not logger.handlers:
    # Обработчик для файла
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Добавляем обработчики к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

logger.info(f'Логгер инициализирован. Логи будут записываться в {log_file}')
