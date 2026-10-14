"""Paths and connection settings, taken from environment variables (see docker-compose.yml)."""
import os
from pathlib import Path

import yaml

APP_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = APP_DIR / 'config'
MIGRATIONS_DIR = APP_DIR / 'migrations'
RULES_DIR = APP_DIR / 'rules'

RAW_DIR = Path(os.environ.get('RAW_DIR', APP_DIR.parent / 'data' / 'raw'))
CACHE_DIR = Path(os.environ.get('CACHE_DIR', APP_DIR.parent / 'data' / 'cache'))
REPORT_DIR = Path(os.environ.get('REPORT_DIR', APP_DIR.parent / 'data' / 'reports'))
DATABASE_URL = os.environ.get('DATABASE_URL', '')


def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name) as fh:
        return yaml.safe_load(fh)


def sources() -> dict:
    return load_yaml('sources.yaml')['years']


def layouts() -> dict:
    return load_yaml('layouts.yaml')
