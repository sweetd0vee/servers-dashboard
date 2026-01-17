import logging
import uuid
from datetime import datetime

import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
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


def insert_data(df: pd.DataFrame):
    connection = psycopg2.connect(
        dbname=DB_CONFIG['database'],
        user=DB_CONFIG['user'],
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        password=DB_CONFIG['password']
    )
    cur = connection.cursor()
    for i in tqdm(range(len(df))):
        row = list(df.iloc[i])
        # date and created_date Timestamp object to string
        row[2] = row[2].strftime('%Y-%m-%d %H:%M:%S')
        row[-1] = row[-1].strftime('%Y-%m-%d %H:%M:%S')
        row = tuple(row)
        query = f"INSERT INTO server_metrics_fact (id, vm, timestamp, metric, value, created_at) \n" \
                f"VALUES {row}"
        try:
            cur.execute(query)
            connection.commit()
        except Exception as e:
            connection.rollback()
            print(f"Ошибка в ставке данных: {row}, {e}")

    #connection.commit()
    cur.close()
    connection.close()
    return


def main():
    # filepath = r'/Users/sweetd0ve/servers-dashboard/data/dbdata/data_06_01-11_01.xlsx'
    filepath = r'/Users/sweetd0ve/servers-dashboard/data/dbdata/data_25_12-31_12.xlsx'
    df = read_excel_file(filepath)
    prepared_data = prepare_data(df)
    insert_data(prepared_data)


if __name__ == '__main__':
    main()