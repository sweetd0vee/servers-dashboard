from datetime import datetime, timedelta
import glob
import os
import warnings

import pandas as pd


class DATA:
    def __init__(self):
        # Все 16 метрик встречающихся в данных
        self.metrics = [
            # CPU метрики
            'cpu.ready.summation', 'cpu.usage.average', 'cpu.usagemhz.average',
            # Disk метрики
            'disk.maxtotallatency.latest', 'disk.provisioned.latest',
            'disk.unshared.latest', 'disk.usage.average', 'disk.used.latest',
            # Memory метрики
            'mem.consumed.average', 'mem.overhead.average', 'mem.swapinrate.average',
            'mem.swapoutrate.average', 'mem.usage.average', 'mem.vmmemctl.average',
            # Метрики Сети
            'net.usage.average',
            # Системные метрики
            'sys.uptime.latest']
        self.units = {
            'cpu.ready.summation': 'millisecond',
            'cpu.usage.average': '%',
            'cpu.usagemhz.average': 'MHz',
            'disk.maxtotallatency.latest': 'millisecond',
            'disk.provisioned.latest': 'KB',
            'disk.unshared.latest': 'KB',
            'disk.usage.average': 'KBps',
            'disk.used.latest': 'KB',
            'mem.consumed.average': 'KB',
            'mem.overhead.average': 'KB',
            'mem.swapinrate.average': 'KBps',
            'mem.swapoutrate.average': 'KBps',
            'mem.usage.average': '%',
            'mem.vmmemctl.average': 'KB',
            'net.usage.average': 'KBps',
            'sys.uptime.latest': 'second'
        }


    @staticmethod
    def read_all_vm(file_path='../data/source/all_vm.txt') -> pd.DataFrame:
        """
        Приводим данные из файла по мощностям всех серверов в понятный формат
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Парсим строки
        data = []
        for line in lines:
            # Убираем кавычки и разделяем по запятым
            cleaned_line = line.strip().strip('"').replace('","', ',').replace('"', '')
            parts = cleaned_line.split(',')
            data.append(parts)

        # Создаем DataFrame
        df = pd.DataFrame(data[1:], columns=data[0])

        # Сохраняем результат
        out_file = '../data/processed/all_vm.xlsx'
        try:
            df.to_excel(out_file, index=False)
            print(f"Data successfully saved to {out_file}")
        except Exception as e:
            print(f"Error saving to Excel: {e}")
        return df

    @staticmethod
    def process_temp(folder_path='../data/source/temp',
                     out_file='../data/processed/temp.xlsx') -> pd.DataFrame:
        """
        Подготавливает данные CSV файлов из папки temp/ по серверам за период: с 25-11-2025 по 01-12-2025 (включительно)
        """
        if not os.path.isdir(folder_path):
            raise ValueError(f"Folder '{folder_path}' does not exist or is not a directory")

        files = glob.glob(os.path.join(folder_path, '*.csv'))

        if not files:
            warnings.warn(f"No CSV files found in folder: {folder_path}")
            return pd.DataFrame()

        print(f"Found {len(files)} CSV files in folder: {folder_path}")

        list_of_dfs = []
        for f in files:
            df = pd.read_csv(f)
            list_of_dfs.append(df)

        if not list_of_dfs:
            warnings.warn("No dataframes to concatenate")
            return pd.DataFrame()

        df = pd.concat(list_of_dfs, ignore_index=True)
        print(f"Length of raw dataframe: {len(df)}")

        # Обрабатываем колонки нового файла
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%d.%m.%y %H:%M:%S', errors='coerce')

        # Удаляем строки с некорректными датами
        initial_len = len(df)
        df = df.dropna(subset=['Timestamp'])
        if len(df) < initial_len:
            print(f"Removed {initial_len - len(df)} rows with invalid timestamps")

        df = df.sort_values(by=['VM', 'Metric', 'Timestamp'], ascending=[True, True, True])

        # ['vm', 'metric', 'timestamp'] является индексом в базе данных. Они не должны дублироваться
        initial_len = len(df)
        df = df.drop_duplicates(subset=['VM', 'Metric', 'Timestamp'], keep='last')
        print(f"Removed {initial_len - len(df)} duplicate rows")

        # Оставляем только колонки 'vm', 'timestamp', 'metric', 'value' для занесения в базу с фактами
        # Проверяем наличие колонок перед удалением
        cols_to_drop = ['Unit', 'Date', 'Time']
        cols_to_drop = [col for col in cols_to_drop if col in df.columns]
        if cols_to_drop:
            df.drop(columns=cols_to_drop, inplace=True)

        df.rename(columns={'VM': 'vm',
                           'Timestamp': 'timestamp',
                           'Metric': 'metric',
                           'Value': 'value'}, inplace=True)

        print(f"Length of dataframe after processing: {len(df)}")

        # Статистика по данным
        print(f"Unique VMs: {df['vm'].nunique()}")
        print(f"Unique metrics: {df['metric'].nunique()}")
        print(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")

        # Сохраняем результат
        try:
            # Создаем директорию, если её нет
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            df.to_excel(out_file, index=False)
            print(f"Data successfully saved to {out_file}")
        except Exception as e:
            print(f"Error saving to Excel: {e}")

        return df

    @staticmethod
    def process_data(in_file='../data/source/data.csv',
                     out_file='../data/processed/data.xlsx') -> pd.DataFrame:
        """
        Подготавливаем данные по серверам за период: с 04-12-2025 по 07-12-2025 (включительно)
        """
        try:
            df = pd.read_csv(in_file)
        except FileNotFoundError:
            print(f"File not found: {in_file}")
            return pd.DataFrame()
        except Exception as e:
            print(f"Error reading file: {e}")
            return pd.DataFrame()

        print(f"Length of initial dataframe: {len(df)}")

        # Проверяем наличие колонок перед удалением
        cols_to_drop = ['vCenter', 'Unit', 'Date', 'Time']
        cols_to_drop = [col for col in cols_to_drop if col in df.columns]
        if cols_to_drop:
            df.drop(columns=cols_to_drop, inplace=True)

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
        else:
            print("Warning: No columns to rename found")

        # ['vm', 'metric', 'timestamp'] является индексом в базе данных. Они не должны дублироваться
        initial_len = len(df)
        df = df.drop_duplicates(subset=['vm', 'metric', 'timestamp'], keep='last')
        print(f"Removed {initial_len - len(df)} duplicate rows")

        # Обрабатываем колонки нового файла
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='%d.%m.%y %H:%M:%S', errors='coerce')

        # Удаляем строки с некорректными датами
        initial_len = len(df)
        df = df.dropna(subset=['timestamp'])
        if len(df) < initial_len:
            print(f"Removed {initial_len - len(df)} rows with invalid timestamps")

        df = df.sort_values(by=['vm', 'metric', 'timestamp'], ascending=[True, True, True])

        # Статистика по данным
        print(f"Length of dataframe after processing: {len(df)}")
        print(f"Unique VMs: {df['vm'].nunique()}")
        print(f"Unique metrics: {df['metric'].nunique()}")
        print(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")

        # Сохраняем результат
        try:
            # Создаем директорию, если её нет
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            df.to_excel(out_file, index=False)
            print(f"Data successfully saved to {out_file}")
        except Exception as e:
            print(f"Error saving to Excel: {e}")

        return df

    @staticmethod
    def pivot_metrics(df: pd.DataFrame, out_file: str) -> pd.DataFrame:
        """
        Приводит датафрейм с колонками ['vm', 'metric', 'timestamp', 'value'] в формат сводной таблицы
        по каждой метрике
        """
        if df.empty:
            print("Empty dataframe provided, cannot create pivot table")
            return pd.DataFrame()

        # Проверяем наличие необходимых колонок
        required_cols = ['vm', 'timestamp', 'metric', 'value']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"Missing required columns for pivot: {missing_cols}")
            return pd.DataFrame()

        try:
            df_wide = df.pivot_table(
                index=['vm', 'timestamp'],
                columns='metric',
                values='value',
                aggfunc='first'  # на случай дублей
            ).reset_index()

            # Переименуем колонки, чтобы убрать multiindex
            df_wide.columns.name = None

            # ВАЖНО: Исправляем сортировку - убираем 'metric' из sort_values
            df_wide = df_wide.sort_values(['vm', 'timestamp'], ascending=[True, True]).reset_index(drop=True)

            print(f"Created pivot dataframe with {len(df_wide)} rows and {len(df_wide.columns)} columns")
            print(f"Metrics in pivot table: {[col for col in df_wide.columns if col not in ['vm', 'timestamp']]}")

            # Сохраняем результат
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            df_wide.to_excel(out_file, index=False)
            print(f"Pivot table successfully saved to {out_file}")

        except Exception as e:
            print(f"Error creating pivot table: {e}")
            return pd.DataFrame()

        return df_wide

    def analyze_data(self, df: pd.DataFrame) -> dict:
        """
        Анализирует данные и возвращает статистику
        """
        if df.empty:
            return {}

        analysis = {
            'total_rows': len(df),
            'unique_vms': df['vm'].nunique() if 'vm' in df.columns else 0,
            'unique_metrics': df['metric'].nunique() if 'metric' in df.columns else 0,
            'time_range': None,
            'missing_metrics': [],
            'data_completeness': {}
        }

        if 'timestamp' in df.columns and not df['timestamp'].isna().all():
            analysis['time_range'] = {
                'start': df['timestamp'].min(),
                'end': df['timestamp'].max(),
                'days': (df['timestamp'].max() - df['timestamp'].min()).days
            }

        # Проверяем полноту метрик
        if 'metric' in df.columns:
            present_metrics = df['metric'].unique()
            missing_metrics = [m for m in self.metrics if m not in present_metrics]
            analysis['missing_metrics'] = missing_metrics

            # Вычисляем полноту данных по каждой метрике
            for metric in self.metrics:
                if metric in present_metrics:
                    metric_data = df[df['metric'] == metric]
                    analysis['data_completeness'][metric] = {
                        'count': len(metric_data),
                        'vms': metric_data['vm'].nunique() if 'vm' in metric_data.columns else 0,
                        'completeness_percentage': round(len(metric_data) / len(df) * 100, 2)
                    }

        return analysis

    def process_data_metric(self, data_source: str,
                            vm: str,
                            metric: str,
                            start_date: datetime,
                            end_date: datetime) -> pd.DataFrame:
        """
        Обрабатывает данные для конкретной метрики в заданный период времени.

        Parameters:
        -----------
        data_source : str
            Источник данных ('temp' или 'data')
        metric : str
            Название метрики для фильтрации
        start_date : datetime
            Начальная дата периода
        end_date : datetime
            Конечная дата периода

        Returns:
        --------
        pd.DataFrame
            Отфильтрованный датафрейм с данными по указанной метрике
        """
        # Определяем путь к файлу в зависимости от источника данных
        if data_source == 'temp':
            data_path = '../data/source/temp.xlsx'
        elif data_source == 'data':
            data_path = '../data/source/data.xlsx'
        else:
            raise ValueError(f"Неизвестный источник данных: {data_source}. "
                             f"Допустимые значения: 'temp', 'data'")

        # Проверяем существование файла
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"Файл данных не найден: {data_path}")

        # Проверяем, что метрика существует в списке метрик
        if metric not in self.metrics:
            available_metrics = [m for m in self.metrics if m.startswith(metric.split('.')[0])]
            print(f"Предупреждение: Метрика '{metric}' не найдена в списке доступных метрик.")
            if available_metrics:
                print(f"Возможно вы имели в виду: {available_metrics[:5]}")  # Показываем первые 5 похожих

        try:
            # Загружаем данные
            df = pd.read_excel(data_path)
            print(f"Загружено {len(df)} строк из файла {data_path}")

        except Exception as e:
            raise Exception(f"Ошибка при загрузке данных из {data_path}: {e}")

        # Проверяем наличие необходимых колонок
        required_cols = ['vm', 'timestamp', 'metric', 'value']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"В файле отсутствуют необходимые колонки: {missing_cols}")

        # Преобразуем timestamp к datetime если это еще не сделано
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

        # Фильтруем по метрике
        df_filtered = df[df['metric'] == metric].copy()

        if df_filtered.empty:
            # Если метрика не найдена, показываем доступные метрики
            available_metrics = df['metric'].unique()
            print(f"Метрика '{metric}' не найдена в данных.")
            print(f"Доступные метрики: {list(available_metrics)[:20]}...")  # Показываем первые 20
            return pd.DataFrame()

        print(f"Найдено {len(df_filtered)} записей для метрики '{metric}'")

        # Фильтруем по дате
        mask = (df_filtered['timestamp'] >= start_date) & (df_filtered['timestamp'] <= end_date)
        df_filtered = df_filtered[mask].copy()
        df_filtered = df_filtered[df_filtered['vm']==vm]

        if df_filtered.empty:
            print(f"Нет данных для vm '{vm}' и метрики '{metric}' в период с {start_date.date()} по {end_date.date()}")
            return pd.DataFrame()

        print(f"После фильтрации по датам осталось {len(df_filtered)} записей")

        # Сортируем данные
        df_filtered = df_filtered.sort_values(['vm', 'timestamp'], ascending=[True, True])

        out_file = f"../data/processed/{vm}_{metric}_{start_date}_{end_date}.xlsx"
        # Сохраняем результат
        try:
            df_filtered.to_excel(out_file, index=False)
            print(f"Data successfully saved to {out_file}")
        except Exception as e:
            print(f"Error saving to Excel: {e}")

        return df_filtered


def run_preprocessing():
    # Создаем объект класса DATA для подготовки данных для работы из исходников
    data = DATA()

    # 1. Готовим данные значений метрик выгруженные по 20 серверам за период: с 25-11-2025 по 01-12-2025 (включительно)
    # Папка с данными data/source/temp/ собранный датафрейм сохраняется в файл data/processed/temp.xlsx
    print("=" * 60)
    print("Processing temp data...")
    print("=" * 60)
    df1 = data.process_temp(folder_path='../data/source/temp',
                            out_file='../data/processed/temp.xlsx')

    if not df1.empty:
        print("\nAnalysis of temp data:")
        analysis1 = data.analyze_data(df1)
        print(f"Total rows: {analysis1.get('total_rows', 0)}")
        print(f"Unique VMs: {analysis1.get('unique_vms', 0)}")
        print(f"Unique metrics: {analysis1.get('unique_metrics', 0)}")

    # 2. Готовим данные значений метрик выгруженные по всем серверам и сферам за период: с 04-12-2025 по 07-12-2025 (включительно)
    # Исходник находится в файле data/source/data.csv и сохраняется в файл data/processed/data.xlsx
    print("\n" + "=" * 60)
    print("Processing data.csv...")
    print("=" * 60)
    df2 = data.process_data(in_file='../data/source/data.csv',
                            out_file='../data/processed/data.xlsx')

    if not df2.empty:
        print("\nAnalysis of data.csv:")
        analysis2 = data.analyze_data(df2)
        print(f"Total rows: {analysis2.get('total_rows', 0)}")
        print(f"Unique VMs: {analysis2.get('unique_vms', 0)}")
        print(f"Unique metrics: {analysis2.get('unique_metrics', 0)}")

    # 3. Далее создаем сводную таблицу по этим серверам и метрикам
    if not df1.empty:
        print("\n" + "=" * 60)
        print("Creating pivot table for temp data...")
        print("=" * 60)
        df_wide1 = data.pivot_metrics(df1, out_file='../data/processed/temp_pivot.xlsx')

    if not df2.empty:
        print("\n" + "=" * 60)
        print("Creating pivot table for data.csv...")
        print("=" * 60)
        df_wide2 = data.pivot_metrics(df2, out_file='../data/processed/data_pivot.xlsx')

    print("\n" + "=" * 60)
    print("Processing completed!")
    print("=" * 60)


if __name__ == '__main__':
    # Создаем объект класса DATA для подготовки данных для работы из исходников
    data = DATA()

    # Сохраняем данные о виртуальных серверах в xlsx файл
    # df = data.read_all_vm('../data/source/all_vm.txt')

    # Подготавливаем данные
    # run_preprocessing()

    # Тестируем выгрузку данных для одного сервера и одной метрики за определенный период времени
    df_train = data.process_data_metric('temp',
                                           'DataLake-DBN1',
                                           'cpu.usage.average',
                                           pd.to_datetime('2025-11-25 17:00:00'),
                                           pd.to_datetime('2025-11-30 23:30:00'))

    df_test = data.process_data_metric('temp',
                                        'DataLake-DBN1',
                                       'cpu.usage.average',
                                       pd.to_datetime('2025-12-01 00:00:00'),
                                       pd.to_datetime('2025-12-01 23:30:00'))