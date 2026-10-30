"""SIEIS Pytest Test Fixtures and Configurations."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

# Add backend directory to sys.path so backend modules are directly importable
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app
from config import TestConfig
from database import Database


@pytest.fixture
def app():
    """Provides a fresh Flask application instance with in-memory database."""
    app_instance = create_app(TestConfig)
    return app_instance


@pytest.fixture
def client(app):
    """Provides a test client for sending HTTP requests."""
    return app.test_client()


@pytest.fixture
def db():
    """Provides an isolated in-memory SQLite database instance."""
    return Database(":memory:")
