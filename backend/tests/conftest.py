"""Shared test fixtures and helpers."""

from __future__ import annotations

import os

# ------------------------------------------------------------------
# Prevent LiteLLM from making any network calls during tests/startup
# ------------------------------------------------------------------
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["LITELLM_MODE"] = "PRODUCTION"

import pytest

# ------------------------------------------------------------------
# Set env vars BEFORE any app module is imported (module-level Settings).
# ------------------------------------------------------------------
os.environ.setdefault("LLM_API_KEYS", "test-key-aaa,test-key-bbb")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_placeholder.db")
os.environ.setdefault("ALLOWED_ORIGINS", "*")
os.environ.setdefault("ENABLE_FAILURE_SIMULATION", "true")
os.environ.setdefault("LLM_MODEL", "gemini/gemini-2.0-flash")
os.environ.setdefault("CACHE_DIR", "test_cache_placeholder")


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """Give every test its own SQLite file and cache dir."""
    db_file = str(tmp_path / "test.db")
    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir, exist_ok=True)

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("CACHE_DIR", cache_dir)
    monkeypatch.setenv("LLM_API_KEYS", "test-key-aaa,test-key-bbb")
    monkeypatch.setenv("ENABLE_FAILURE_SIMULATION", "true")

    # Rebuild settings from updated env
    from backend.app.config import Settings
    from backend.app import config as cfg_mod
    new_settings = Settings()
    monkeypatch.setattr(cfg_mod, "settings", new_settings)

    # Reset DB connection so it uses the new db path
    from backend.app import db as db_mod
    db_mod._connection = None

    # Re-setup cache with new dir
    from backend.app import llm_gateway as gw
    gw.setup_cache()

    yield

    db_mod.close_connection()


@pytest.fixture()
def client():
    """Return a TestClient for the FastAPI app."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    return TestClient(app, raise_server_exceptions=False)
