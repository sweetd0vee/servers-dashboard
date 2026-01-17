"""
Data loader for dashboard - loads data from database instead of generating
"""
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# Add path to app modules
current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.join(current_dir, '..', '..', 'app')
sys.path.insert(0, app_dir)

try:
    import models as db_models
    from connection import SessionLocal
    from dbcrud import DBCRUD
    from facts_crud import FactsCRUD
except ImportError as e:
    print(f"Warning: Could not import database modules: {e}")
    print("Falling back to mock data generation")
    SessionLocal = None


def get_db_session():
    """Get database session"""
    if SessionLocal is None:
        return None
    return SessionLocal()


def load_server_data_from_db(
    hours: int = 720,  # Last 30 days by default
    vms: Optional[List[str]] = None,
    metrics: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Load server metrics data from database
    
    Args:
        hours: Number of hours of data to load (default: 720 = 30 days)
        vms: Optional list of VM names to filter. If None, loads all VMs
        metrics: Optional list of metrics to load. If None, loads all metrics
        
    Returns:
        DataFrame with columns: server, timestamp, and various metric columns
    """
    if SessionLocal is None:
        # Fallback to empty DataFrame if database not available
        return pd.DataFrame()
    
    db = get_db_session()
    if db is None:
        return pd.DataFrame()
    
    try:
        crud_db = DBCRUD(db)
        crud_facts = FactsCRUD(db)
        
        # Get list of VMs if not specified
        if vms is None:
            vms = crud_db.get_all_vms()
            if not vms:
                return pd.DataFrame()
        
        # Default metrics if not specified
        if metrics is None:
            # Get metrics from first VM (assuming all VMs have similar metrics)
            if vms:
                metrics = crud_db.get_metrics_for_vm(vms[0])
            else:
                metrics = ['cpu.usage.average']  # Default metric
        
        # Calculate start date
        start_date = datetime.now() - timedelta(hours=hours)
        
        # Collect all data
        all_data = []
        
        for vm in vms:
            for metric in metrics:
                try:
                    # Get metrics for this VM and metric
                    records = crud_facts.get_metrics_fact(
                        vm=vm,
                        metric=metric,
                        start_date=start_date,
                        limit=10000  # Limit to prevent memory issues
                    )
                    
                    for record in records:
                        all_data.append({
                            'vm': vm,
                            'timestamp': record.timestamp,
                            'metric': metric,
                            'value': float(record.value) if record.value else 0.0
                        })
                except Exception as e:
                    print(f"Error loading data for {vm}/{metric}: {e}")
                    continue
        
        if not all_data:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(all_data)
        
        # Pivot to wide format (one column per metric)
        df_pivot = df.pivot_table(
            index=['vm', 'timestamp'],
            columns='metric',
            values='value',
            aggfunc='mean'  # In case of duplicates
        ).reset_index()
        
        # Rename vm to server for compatibility
        df_pivot = df_pivot.rename(columns={'vm': 'server'})
        
        # Calculate load_percentage (use cpu.usage.average as default)
        if 'cpu.usage.average' in df_pivot.columns:
            df_pivot['load_percentage'] = df_pivot['cpu.usage.average']
        else:
            # Use first available metric or average of all metrics
            metric_cols = [col for col in df_pivot.columns if col not in ['server', 'timestamp']]
            if metric_cols:
                df_pivot['load_percentage'] = df_pivot[metric_cols[0]]
            else:
                df_pivot['load_percentage'] = 0.0
        
        # Add derived columns for compatibility with UI
        df_pivot['server_type'] = df_pivot['server'].str.split('-').str[0]
        df_pivot['weekday'] = pd.to_datetime(df_pivot['timestamp']).dt.weekday
        df_pivot['hour_of_day'] = pd.to_datetime(df_pivot['timestamp']).dt.hour
        df_pivot['is_business_hours'] = (
            (df_pivot['hour_of_day'] >= 9) & (df_pivot['hour_of_day'] <= 17)
        ).astype(int)
        df_pivot['is_weekend'] = (df_pivot['weekday'] >= 5).astype(int)
        
        # Add missing columns with default values if needed
        expected_columns = [
            'cpu.usage.average', 'mem.usage.average', 'net.usage.average',
            'cpu.ready.summation', 'disk.usage.average', 'errors'
        ]
        
        for col in expected_columns:
            if col not in df_pivot.columns:
                # Try to find similar metric
                similar = [c for c in df_pivot.columns if col.split('.')[0] in c.lower()]
                if similar:
                    df_pivot[col] = df_pivot[similar[0]]
                else:
                    df_pivot[col] = 0.0
        
        # Rename columns to match UI expectations
        column_mapping = {
            'memory.usage.average': 'mem.usage.average',
            'net.usage.average': 'net.usage.average',
        }
        df_pivot = df_pivot.rename(columns=column_mapping)
        
        # Add rolling averages
        for server in df_pivot['server'].unique():
            mask = df_pivot['server'] == server
            df_pivot.loc[mask, 'load_ma_6h'] = (
                df_pivot.loc[mask, 'load_percentage']
                .rolling(6, min_periods=1)
                .mean()
            )
            df_pivot.loc[mask, 'load_ma_24h'] = (
                df_pivot.loc[mask, 'load_percentage']
                .rolling(24, min_periods=1)
                .mean()
            )
        
        # Sort by timestamp
        df_pivot = df_pivot.sort_values('timestamp').reset_index(drop=True)
        
        return df_pivot
        
    except Exception as e:
        print(f"Error loading data from database: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()
    finally:
        if db:
            db.close()


def generate_server_data() -> pd.DataFrame:
    """
    Main function to load server data from database.
    This function maintains compatibility with existing UI code.
    
    Returns:
        DataFrame with server metrics data
    """
    # Try to load from database
    df = load_server_data_from_db(hours=720)  # Last 30 days
    
    # If no data in database, return empty DataFrame with expected columns
    if df.empty:
        # Return empty DataFrame with expected structure
        return pd.DataFrame(columns=[
            'server', 'timestamp', 'load_percentage',
            'cpu.usage.average', 'mem.usage.average', 'net.usage.average',
            'cpu.ready.summation', 'disk.usage.average', 'errors',
            'server_type', 'weekday', 'hour_of_day',
            'is_business_hours', 'is_weekend', 'load_ma_6h', 'load_ma_24h'
        ])
    
    return df


def generate_forecast(historical_data: pd.DataFrame, hours: int = 48) -> pd.DataFrame:
    """
    Generate forecast based on historical data.
    This is a simple forecast - in production, use the Prophet forecaster.
    
    Args:
        historical_data: Historical data DataFrame
        hours: Number of hours to forecast
        
    Returns:
        DataFrame with forecast data
    """
    if historical_data.empty:
        return pd.DataFrame()
    
    last_date = pd.to_datetime(historical_data['timestamp']).max()
    forecast_dates = [last_date + timedelta(hours=i) for i in range(1, hours + 1)]
    
    # Simple forecast: use average of last 24 hours with trend
    if 'load_percentage' in historical_data.columns:
        last_values = historical_data['load_percentage'].tail(24).values
        base_forecast = np.mean(last_values) if len(last_values) > 0 else 50.0
    else:
        base_forecast = 50.0
    
    forecast_values = []
    for i, date in enumerate(forecast_dates):
        hour = date.hour
        # Simple seasonality
        if 9 <= hour <= 17:
            seasonality = np.random.normal(15, 3)
        elif 18 <= hour <= 22:
            seasonality = np.random.normal(8, 2)
        else:
            seasonality = np.random.normal(-10, 3)
        
        trend = i * 0.02
        forecast_val = base_forecast + seasonality + trend
        forecast_val = max(5, min(100, forecast_val))
        forecast_values.append(forecast_val)
    
    return pd.DataFrame({
        'timestamp': forecast_dates,
        'load_percentage': forecast_values
    })


# For backward compatibility, keep the old function name
def load_data_from_database(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    vms: Optional[List[str]] = None,
    metrics: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Load data from database with custom date range
    
    Args:
        start_date: Start date for data loading
        end_date: End date for data loading
        vms: Optional list of VM names
        metrics: Optional list of metrics
        
    Returns:
        DataFrame with server metrics
    """
    if SessionLocal is None:
        return pd.DataFrame()
    
    db = get_db_session()
    if db is None:
        return pd.DataFrame()
    
    try:
        crud_facts = FactsCRUD(db)
        
        # Get list of VMs if not specified
        if vms is None:
            crud_db = DBCRUD(db)
            vms = crud_db.get_all_vms()
        
        if not vms:
            return pd.DataFrame()
        
        # Default metrics
        if metrics is None:
            crud_db = DBCRUD(db)
            metrics = crud_db.get_metrics_for_vm(vms[0]) if vms else ['cpu.usage.average']
        
        all_data = []
        
        for vm in vms:
            for metric in metrics:
                try:
                    records = crud_facts.get_metrics_fact(
                        vm=vm,
                        metric=metric,
                        start_date=start_date,
                        end_date=end_date,
                        limit=10000
                    )
                    
                    for record in records:
                        all_data.append({
                            'vm': vm,
                            'timestamp': record.timestamp,
                            'metric': metric,
                            'value': float(record.value) if record.value else 0.0
                        })
                except Exception as e:
                    print(f"Error loading {vm}/{metric}: {e}")
                    continue
        
        if not all_data:
            return pd.DataFrame()
        
        # Convert to DataFrame and pivot
        df = pd.DataFrame(all_data)
        df_pivot = df.pivot_table(
            index=['vm', 'timestamp'],
            columns='metric',
            values='value',
            aggfunc='mean'
        ).reset_index()
        
        df_pivot = df_pivot.rename(columns={'vm': 'server'})
        
        # Add load_percentage
        if 'cpu.usage.average' in df_pivot.columns:
            df_pivot['load_percentage'] = df_pivot['cpu.usage.average']
        else:
            metric_cols = [col for col in df_pivot.columns if col not in ['server', 'timestamp']]
            df_pivot['load_percentage'] = df_pivot[metric_cols[0]] if metric_cols else 0.0
        
        return df_pivot
        
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()
    finally:
        if db:
            db.close()

