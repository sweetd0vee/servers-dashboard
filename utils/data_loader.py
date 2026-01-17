from datetime import datetime
import logging
import uuid

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from tqdm import tqdm


# Конфигурация базы данных
DB_CONFIG = {
    'host': 'localhost',  # или IP-адрес Docker контейнера
    'port': '5432',
    'database': 'server_metrics',  # имя вашей базы данных
    'user': 'postgres',
    'password': 'postgres'  # замените на ваш пароль
}


def read_excel_file(file_path):
    """Чтение данных из Excel файла"""
    try:
        # Читаем Excel файл
        df = pd.read_excel(file_path)

        # Проверяем наличие необходимых колонок
        required_columns = ['vm', 'timestamp', 'metric', 'value']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise ValueError(f"Отсутствуют необходимые колонки: {missing_columns}")

        print(f"Успешно прочитан файл: {file_path}")
        print(f"Количество строк: {len(df)}")
        print(f"Колонки: {df.columns.tolist()}")

        return df

    except Exception as e:
        print(f"Ошибка чтения Excel файла: {e}")
        raise


def prepare_data(df):
    """Подготовка данных для вставки"""
    try:
        # Создаем копию данных
        data = df.copy()

        # Преобразуем дату в формат datetime
        data['timestamp'] = pd.to_datetime(data['timestamp'], format='%y-%m-%d %H:%M:%S', errors='coerce')

        # Проверяем корректность преобразования дат
        invalid_dates = data['timestamp'].isna().sum()
        if invalid_dates > 0:
            print(f"Найдено {invalid_dates} некорректных дат")

        # Преобразуем числовые колонки
        data['value'] = pd.to_numeric(data['value'], errors='coerce')

        # Генерируем UUID для каждой строки
        data['id'] = [str(uuid.uuid4()) for _ in range(len(data))]

        # Добавляем created_at
        data['created_at'] = datetime.now()

        # Выбираем только необходимые колонки в правильном порядке
        final_columns = ['id', 'vm', 'timestamp', 'metric', 'value', 'created_at']
        data = data[final_columns]

        # Удаляем дубли по constraint ['vm', 'timestamp', 'metric']
        original_count = len(data)
        data = data.drop_duplicates(subset=['vm', 'timestamp', 'metric'])
        removed_count = original_count - len(data)
        if removed_count > 0:
            print(f"Удалено {removed_count} строк с дублирующимися значениями по полям [vm, timestamp, metric]")

        # Удаляем строки с NaN значениями в ключевых полях
        original_count = len(data)
        data = data.dropna(subset=['vm', 'timestamp', 'metric'])
        removed_count = original_count - len(data)

        if removed_count > 0:
            print(f"Удалено {removed_count} строк с отсутствующими ключевыми значениями")

        print(f"Подготовлено {len(data)} строк для вставки")

        return data

    except Exception as e:
        print(f"Ошибка подготовки данных: {e}")
        raise


def validate_data_for_insert(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = ['id', 'vm', 'timestamp', 'metric', 'value', 'created_at']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns for insert: {missing_columns}")

    if df.empty:
        raise ValueError("DataFrame is empty, nothing to insert")

    null_counts = df[required_columns].isna().sum()
    if null_counts.any():
        raise ValueError(f"Null values found in required columns: {null_counts.to_dict()}")

    return df[required_columns]


def insert_data(df: pd.DataFrame, batch_size: int = 1000):
    data = validate_data_for_insert(df)
    query = (
        "INSERT INTO server_metrics_fact (id, vm, timestamp, metric, value, created_at) "
        "VALUES %s"
    )

    try:
        with psycopg2.connect(
            dbname=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            password=DB_CONFIG['password'],
        ) as connection:
            with connection.cursor() as cur:
                rows = data.to_records(index=False).tolist()
                for i in tqdm(range(0, len(rows), batch_size), desc="Inserting batches"):
                    batch = rows[i:i + batch_size]
                    execute_values(cur, query, batch)
            connection.commit()
    except Exception as e:
        logging.exception("Insert failed: %s", e)
        raise

    return


def main():
    # filepath = r'/Users/sweetd0ve/servers-dashboard/data/dbdata/data_06_01-11_01.xlsx'
    filepath = r'/Users/sweetd0ve/servers-dashboard/data/dbdata/data_25_12-31_12.xlsx'
    try:
        df = read_excel_file(filepath)
        prepared_data = prepare_data(df)
        insert_data(prepared_data)
        print("Data import completed successfully")
    except Exception as e:
        logging.exception("ETL failed: %s", e)
        raise


if __name__ == '__main__':
    main()