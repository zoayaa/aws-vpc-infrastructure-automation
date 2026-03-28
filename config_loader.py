import yaml
import logging
import os
import json
from datetime import datetime, timezone, timedelta

# Define IST timezone
IST = timezone(timedelta(hours=5, minutes=30))
STATE_FILE = "state.json"

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    with open(config_path, 'r') as stream:
        return yaml.safe_load(stream)

def setup_logging(module_name):
    logger = logging.getLogger(module_name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        formatter.converter = lambda *args: datetime.now(IST).timetuple()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger

def load_state():
    """Loads existing infrastructure IDs from the state file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_state(state_data):
    """Saves infrastructure IDs to ensure we don't lose track of resources."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state_data, f, indent=4)
