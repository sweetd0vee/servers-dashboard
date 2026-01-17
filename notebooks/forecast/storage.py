import os
import pickle
import json
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)


def load_model_with_metadata(model_path: str):
    try:
        with open(model_path, 'rb') as f:
            data = pickle.load(f)
        return data['model'], data
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return None, None


def find_latest_model(model_storage_path: str, vm: str, metric: str):
    try:
        files = [f for f in os.listdir(model_storage_path) if f.startswith(f"{vm}_{metric}_prophet") and f.endswith('.pkl')]
        if not files:
            return None
        files.sort(reverse=True)
        return os.path.join(model_storage_path, files[0])
    except Exception as e:
        logger.warning(f"Failed to find latest model: {e}")
        return None


def cleanup_old_models(model_storage_path: str, days_to_keep: int = 30):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
    deleted = 0
    for f in os.listdir(model_storage_path):
        if f.endswith('.pkl'):
            path = os.path.join(model_storage_path, f)
            mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
            if mtime < cutoff:
                os.remove(path)
                json_path = path.replace('.pkl', '_metrics.json')
                if os.path.exists(json_path):
                    os.remove(json_path)
                deleted += 1
    return deleted
