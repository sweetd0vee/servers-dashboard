"""
Простой скрипт для выгрузки исторических данных временных рядов из базы
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import json

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseExtractor:
    """Класс для выгрузки данных из БД"""
    
    def __init__(self, db_url: str, output_dir: str = None):
        self.db_url = db_url
        self.output_dir = output_dir or os.path.join(os.getcwd(), 'data_extracts')
        self.engine = None
        self.SessionLocal = None
        self._init_database()
        os.makedirs(self.output_dir, exist_ok=True)
        
    def _init_database(self):
        """Инициализация подключения к БД"""
        try:
            self.engine = create_engine(self.db_url)
            self.SessionLocal = sessionmaker(bind=self.engine)
            logger.info(f"Connected to database")
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise
            
    @contextmanager
    def get_session(self):
        """Контекстный менеджер для сессии БД"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_vms(self, session: Session, days: int = 14) -> List[str]:
        """Получение списка виртуальных машин"""
        try:
            start_date = datetime.now() - timedelta(days=days)
            query = text("SELECT DISTINCT vm FROM server_metrics_fact WHERE timestamp >= :date ORDER BY vm")
            result = session.execute(query, {'date': start_date})
            return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Error getting VMs: {e}")
            return []
    
    def get_metrics(self, session: Session, vm: str = None, days: int = 14) -> List[str]:
        """Получение списка метрик"""
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            if vm:
                query = text("SELECT DISTINCT metric FROM server_metrics_fact WHERE vm = :vm AND timestamp >= :date ORDER BY metric")
                params = {'vm': vm, 'date': start_date}
            else:
                query = text("SELECT DISTINCT metric FROM server_metrics_fact WHERE timestamp >= :date ORDER BY metric")
                params = {'date': start_date}
            
            result = session.execute(query, params)
            return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return []
    
    def extract_data(self, session: Session, vm: str, metric: str, days: int = 14) -> pd.DataFrame:
        """Выгрузка данных для VM и метрики"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            query = text("""
                SELECT timestamp, value 
                FROM server_metrics_fact
                WHERE vm = :vm AND metric = :metric 
                AND timestamp >= :start AND timestamp <= :end
                ORDER BY timestamp
            """)
            
            params = {
                'vm': vm,
                'metric': metric,
                'start': start_date,
                'end': end_date
            }
            
            result = session.execute(query, params)
            data = result.fetchall()
            
            if not data:
                logger.warning(f"No data found for {vm}.{metric}")
                return pd.DataFrame()
            
            df = pd.DataFrame(data, columns=['timestamp', 'value'])
            logger.info(f"Extracted {len(df)} rows for {vm}.{metric}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error extracting data: {e}")
            return pd.DataFrame()
    
    def prepare_for_prophet(self, df: pd.DataFrame) -> pd.DataFrame:
        """Подготовка данных для Prophet"""
        if df.empty:
            return df
        
        # Переименовываем колонки
        result = df.rename(columns={'timestamp': 'ds', 'value': 'y'})
        
        # Конвертируем типы
        result['ds'] = pd.to_datetime(result['ds'])
        result['y'] = pd.to_numeric(result['y'], errors='coerce')
        
        # Сортируем и удаляем дубликаты
        result = result.sort_values('ds').drop_duplicates(subset=['ds'])
        
        # Удаляем NaN
        result = result.dropna(subset=['y'])
        
        logger.info(f"Prepared {len(result)} rows for Prophet")
        return result
    
    def save_data(self, df: pd.DataFrame, vm: str, metric: str) -> str:
        """Сохранение данных в файл"""
        if df.empty:
            logger.warning("No data to save")
            return ""
        
        # Создаем имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_vm = vm.replace('/', '_').replace('\\', '_')
        safe_metric = metric.replace('/', '_').replace('\\', '_')
        filename = f"{safe_vm}_{safe_metric}_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)
        
        # Сохраняем
        df.to_csv(filepath, index=False)
        logger.info(f"Saved to {filepath}")
        
        # Сохраняем метаданные
        metadata = {
            'vm': vm,
            'metric': metric,
            'extracted_at': datetime.now().isoformat(),
            'rows': len(df),
            'date_range': {
                'start': df['ds'].min().isoformat() if not df.empty else None,
                'end': df['ds'].max().isoformat() if not df.empty else None
            }
        }
        
        metadata_file = filepath.replace('.csv', '_meta.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        return filepath


def main():
    """Основная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Выгрузка данных временных рядов')
    parser.add_argument('--vm', help='Имя виртуальной машины')
    parser.add_argument('--metric', help='Имя метрики')
    parser.add_argument('--days', type=int, default=14, help='Количество дней (по умолчанию: 14)')
    parser.add_argument('--list-vms', action='store_true', help='Показать список VMs')
    parser.add_argument('--list-metrics', action='store_true', help='Показать список метрик')
    parser.add_argument('--db-url', default='postgresql://postgres:postgres@localhost:5432/server_metrics',
                       help='URL базы данных')
    parser.add_argument('--output-dir', default=r'C:\Users\audit\Work\Arina\Servers\dashboard\data\dbextract',
                       help='Директория для сохранения')
    
    args = parser.parse_args()
    
    # Создаем экстрактор
    extractor = DatabaseExtractor(args.db_url, args.output_dir)
    
    try:
        if args.list_vms:
            # Показать список VMs
            with extractor.get_session() as session:
                vms = extractor.get_vms(session, args.days)
                print(f"\nНайдено {len(vms)} виртуальных машин:")
                for vm in vms:
                    print(f"  - {vm}")
                    
        elif args.list_metrics:
            # Показать список метрик
            with extractor.get_session() as session:
                metrics = extractor.get_metrics(session, args.vm, args.days)
                title = "метрик" if not args.vm else f"метрик для VM '{args.vm}'"
                print(f"\nНайдено {len(metrics)} {title}:")
                for metric in metrics:
                    print(f"  - {metric}")
                    
        elif args.vm and args.metric:
            # Выгрузить данные
            with extractor.get_session() as session:
                # Получаем данные
                df = extractor.extract_data(session, args.vm, args.metric, args.days)
                
                if df.empty:
                    print(f"\nДанные не найдены для {args.vm}.{args.metric}")
                    return
                
                # Подготавливаем для Prophet
                prophet_df = extractor.prepare_for_prophet(df)
                
                if prophet_df.empty:
                    print(f"\nНет валидных данных для подготовки")
                    return
                
                # Сохраняем
                filepath = extractor.save_data(prophet_df, args.vm, args.metric)
                
                if filepath:
                    print(f"\n✅ Данные успешно сохранены в: {filepath}")
                    print(f"\nПервые 5 строк:")
                    print(prophet_df.head())
                    print(f"\nСтатистика:")
                    print(f"  Всего записей: {len(prophet_df)}")
                    print(f"  Период: {prophet_df['ds'].min()} - {prophet_df['ds'].max()}")
                    
        else:
            print("\nИспользование:")
            print("  python script.py --list-vms                    # Показать список VMs")
            print("  python script.py --list-metrics --vm <имя_vm>  # Показать метрики для VM")
            print("  python script.py --vm <имя> --metric <метрика> # Выгрузить данные")
            print("\nОпции:")
            print("  --days N      Количество дней для выгрузки (по умолчанию: 14)")
            print("  --db-url      URL базы данных")
            print("  --output-dir  Директория для сохранения")
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    main()