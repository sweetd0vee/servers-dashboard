import os

import pandas as pd


def read_csv_special(file_path: str):
    """
    Читает CSV файл в формате, где каждая строка целиком заключена в кавычки,
    а поля разделены запятыми внутри кавычек.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Удаляем кавычки из всего файла
    # 1. Заменяем разделители '","' на стандартные разделители
    content = content.replace('","', '|||')  # Временный разделитель

    # 2. Удаляем все оставшиеся кавычки
    content = content.replace('"', '')

    # 3. Восстанавливаем нормальные разделители
    content = content.replace('|||', ',')

    # Читаем очищенный CSV
    from io import StringIO
    return pd.read_csv(StringIO(content))


def process_new_data(in_file='../data/source/08_01-11_01.txt',
                     out_file='../data/processed/data08_01-11_01.xlsx') -> pd.DataFrame:
    """Читаем новый чанк данных за 08.01 по 11.01"""
    try:
        # Читаем CSV с правильными параметрами для вашего формата
        df = read_csv_special(in_file)

    except FileNotFoundError:
        print(f"File not found: {in_file}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error reading file: {e}")
        return pd.DataFrame()
    
    print(f"Length of initial dataframe: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    print(f"\nFirst few rows:")
    print(df.head())    

    # Проверяем наличие колонок перед удалением
    cols_to_drop = ['VM_System', 'VM_CPU_Count', 'VM_RAM_GB', 'vCenter', 'Unit', 'Date', 'Time']
    cols_to_drop = [col for col in cols_to_drop if col in df.columns]
    if cols_to_drop:
        df.drop(columns=cols_to_drop, inplace=True)
        print(f"\nDropped columns: {cols_to_drop}")

    # Проверяем наличие колонок для переименования
    rename_dict = {
        'VM_Name': 'vm',
        'Metric': 'metric',
        'Value': 'value',
        'Timestamp': 'timestamp'
    }

    # Переименовываем только существующие колонки
    rename_mapping = {old: new for old, new in rename_dict.items() if old in df.columns}
    if rename_mapping:
        df.rename(columns=rename_mapping, inplace=True)
        print(f"\nRenamed columns: {rename_mapping}")
    else:
        print("\nWarning: No columns to rename found")

    # Проверяем наличие необходимых колонок
    required_columns = ['vm', 'metric', 'timestamp', 'value']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"\nError: Missing required columns: {missing_columns}")
        return pd.DataFrame()

    # ['vm', 'metric', 'timestamp'] является индексом в базе данных. Они не должны дублироваться
    initial_len = len(df)
    df = df.drop_duplicates(subset=['vm', 'metric', 'timestamp'], keep='last')
    print(f"\nRemoved {initial_len - len(df)} duplicate rows")

    # Обрабатываем колонки нового файла
    print(f"\nConverting timestamp column...")
    print(f"Timestamp sample before conversion: {df['timestamp'].iloc[0]}")

    df['timestamp'] = pd.to_datetime(df['timestamp'], format='%d.%m.%y %H:%M:%S', errors='coerce')

    # Удаляем строки с некорректными датами
    initial_len = len(df)
    df = df.dropna(subset=['timestamp'])
    if len(df) < initial_len:
        print(f"Removed {initial_len - len(df)} rows with invalid timestamps")

    # Преобразуем value в числовой формат, если возможно
    print(f"\nConverting value column to numeric...")
    df['value'] = pd.to_numeric(df['value'], errors='coerce')

    df = df.sort_values(by=['vm', 'metric', 'timestamp'], ascending=[True, True, True])

    # Статистика по данным
    print(f"\n=== Statistics ===")
    print(f"Length of dataframe after processing: {len(df)}")
    print(f"Unique VMs: {df['vm'].nunique()}")
    print(f"Unique metrics: {df['metric'].nunique()}")
    print(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"\nSample of processed data:")
    print(df.head())

    # Сохраняем результат
    try:
        # Создаем директорию, если её нет
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        df.to_excel(out_file, index=False)
        print(f"\nData successfully saved to {out_file}")
    except Exception as e:
        print(f"Error saving to Excel: {e}")

    return df


def process_data(in_file='../data/source/data_25-12_31_12.csv',
                 out_file='../data/processed/data_25-12_31_12.xlsx') -> pd.DataFrame:
    """
    Подготавливаем данные по серверам за период: с 25-12-2025 по 31-12-2025 (включительно)
    Сделаем пока как было потом пересоздам таблицу под формат новых данных, так будет удобнее рисовать дашборды
    """
    try:
        # Читаем CSV с правильными параметрами для вашего формата
        df = read_csv_special(in_file)

    except FileNotFoundError:
        print(f"File not found: {in_file}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error reading file: {e}")
        return pd.DataFrame()

    print(f"Length of initial dataframe: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    print(f"\nFirst few rows:")
    print(df.head())

    # Проверяем наличие колонок перед удалением
    cols_to_drop = ['VM_System', 'VM_CPU_Count', 'VM_RAM_GB', 'vCenter', 'Unit', 'Date', 'Time']
    cols_to_drop = [col for col in cols_to_drop if col in df.columns]
    if cols_to_drop:
        df.drop(columns=cols_to_drop, inplace=True)
        print(f"\nDropped columns: {cols_to_drop}")

    # Проверяем наличие колонок для переименования
    rename_dict = {
        'VM_Name': 'vm',
        'Metric': 'metric',
        'Value': 'value',
        'Timestamp': 'timestamp'
    }

    # Переименовываем только существующие колонки
    rename_mapping = {old: new for old, new in rename_dict.items() if old in df.columns}
    if rename_mapping:
        df.rename(columns=rename_mapping, inplace=True)
        print(f"\nRenamed columns: {rename_mapping}")
    else:
        print("\nWarning: No columns to rename found")

    # Проверяем наличие необходимых колонок
    required_columns = ['vm', 'metric', 'timestamp', 'value']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"\nError: Missing required columns: {missing_columns}")
        return pd.DataFrame()

    # ['vm', 'metric', 'timestamp'] является индексом в базе данных. Они не должны дублироваться
    initial_len = len(df)
    df = df.drop_duplicates(subset=['vm', 'metric', 'timestamp'], keep='last')
    print(f"\nRemoved {initial_len - len(df)} duplicate rows")

    # Обрабатываем колонки нового файла
    print(f"\nConverting timestamp column...")
    print(f"Timestamp sample before conversion: {df['timestamp'].iloc[0]}")

    df['timestamp'] = pd.to_datetime(df['timestamp'], format='%d.%m.%y %H:%M:%S', errors='coerce')

    # Удаляем строки с некорректными датами
    initial_len = len(df)
    df = df.dropna(subset=['timestamp'])
    if len(df) < initial_len:
        print(f"Removed {initial_len - len(df)} rows with invalid timestamps")

    # Преобразуем value в числовой формат, если возможно
    print(f"\nConverting value column to numeric...")
    df['value'] = pd.to_numeric(df['value'], errors='coerce')

    df = df.sort_values(by=['vm', 'metric', 'timestamp'], ascending=[True, True, True])

    # Статистика по данным
    print(f"\n=== Statistics ===")
    print(f"Length of dataframe after processing: {len(df)}")
    print(f"Unique VMs: {df['vm'].nunique()}")
    print(f"Unique metrics: {df['metric'].nunique()}")
    print(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"\nSample of processed data:")
    print(df.head())

    # Сохраняем результат
    try:
        # Создаем директорию, если её нет
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        df.to_excel(out_file, index=False)
        print(f"\nData successfully saved to {out_file}")
    except Exception as e:
        print(f"Error saving to Excel: {e}")

    return df


if __name__ == '__main__':
    # Для тестирования с вашим тестовым файлом
    # df = process_data('../data/source/data_25-12_31_12.csv', '../data/processed/data_25-12_31_12.xlsx')

    # if not df.empty:
    #     print(f"\nFinal DataFrame shape: {df.shape}")
    #     print(f"Columns: {list(df.columns)}")
    #     print("\nFirst 10 rows:")
    #     print(df.head(10))

    # df = read_csv_special('../data/source/data_25-12_31_12.csv')
    # df.to_excel('../data/processed/data_25-12_31_12_raw.xlsx')

    # df = pd.read_excel('../data/processed/datalake_cpu.xlsx')
    # # Создание сводной таблицы
    # pivot_table = df.pivot_table(
    #     index='vm',  # Строки - серверы
    #     columns='timestamp',  # Столбцы - временные метки
    #     values='value',  # Значения - метрики CPU
    #     aggfunc='first'  # Берем первое значение для каждого сервера+время
    # )

    # # Если хотите получить таблицу без мультииндексов:
    # pivot_table = pivot_table.reset_index()

    # # Переименовываем столбец с серверами (опционально)
    # pivot_table = pivot_table.rename_axis(None, axis=1)

    # # Сохраняем результат в новый Excel файл
    # pivot_table.to_excel('../data/processed/datalake_cpu_pivot.xlsx', index=False)

    # # Показать первые несколько строк
    # print("Сводная таблица создана. Первые 5 строк:")
    # print(pivot_table.head())
    # print(f"\nРазмер таблицы: {pivot_table.shape}")
    # print(f"Количество серверов: {len(pivot_table)}")
    # print(f"Количество временных меток: {len(pivot_table.columns) - 1}")  # -1 для столбца 'vm'

    # Готовим самые новые данные
    df = process_new_data(in_file=r'C:\Users\audit\Work\Arina\Servers\dashboard\data\source\08_01-11_01.txt',
                          out_file=r'C:\Users\audit\Work\Arina\Servers\dashboard\data\processed\data08_01-11_01.xlsx')
    print(df.head())

