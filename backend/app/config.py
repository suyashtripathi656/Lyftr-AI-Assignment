"""Application configuration — all settings come from environment variables."""

from __future__ import annotations

import logging
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Load .env from current directory or parent directory
    load_dotenv()
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

logger = logging.getLogger("config")


class Settings:
    """Validated application settings.  Created lazily via get_settings()."""

    def __init__(self) -> None:
        # --- API key pool ---------------------------------------------------
        raw_keys = os.environ.get("LLM_API_KEYS", "")
        self.api_keys: list[str] = [k.strip() for k in raw_keys.split(",") if k.strip()]

        # key_id mapping: key_1, key_2, ...
        self.key_ids: dict[str, str] = {
            key: f"key_{i+1}" for i, key in enumerate(self.api_keys)
        }

        # --- Database --------------------------------------------------------
        self.database_url: str = os.environ.get("DATABASE_URL", "sqlite:////data/app.db")
        # Extract the file path from the URL
        if self.database_url.startswith("sqlite:///"):
            raw_path = self.database_url.replace("sqlite:///", "", 1)
        else:
            raw_path = self.database_url

        # On Windows, if path is /data/... map it to the local workspace ./data/...
        if os.name == "nt" and (raw_path.startswith("/data") or raw_path.startswith("\\data")):
            clean_rel = raw_path.lstrip("/\\")
            self.db_path: str = str((Path(__file__).resolve().parent.parent.parent / clean_rel).resolve())
        else:
            self.db_path = raw_path

        # --- CORS ------------------------------------------------------------
        raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
        self.allowed_origins: list[str] = [o.strip() for o in raw_origins.split(",") if o.strip()]

        # --- Feature flags ---------------------------------------------------
        self.enable_failure_simulation: bool = (
            os.environ.get("ENABLE_FAILURE_SIMULATION", "false").lower() == "true"
        )

        # --- LLM -------------------------------------------------------------
        self.llm_model: str = os.environ.get("LLM_MODEL", "gemini/gemini-2.0-flash")
        self.default_system_prompt: str = os.environ.get(
            "DEFAULT_SYSTEM_PROMPT",
            "You are a helpful AI assistant.",
        )

        # --- Cache -----------------------------------------------------------
        raw_cache = os.environ.get("CACHE_DIR", "/data/cache")
        if os.name == "nt" and (raw_cache.startswith("/data") or raw_cache.startswith("\\data")):
            clean_cache = raw_cache.lstrip("/\\")
            self.cache_dir: str = str((Path(__file__).resolve().parent.parent.parent / clean_cache).resolve())
        else:
            self.cache_dir = raw_cache

        # --- History ---------------------------------------------------------
        self.max_history_messages: int = int(
            os.environ.get("MAX_HISTORY_MESSAGES", "40")
        )

    def validate(self) -> None:
        """Raise if critical config is missing.  Called at startup."""
        if len(self.api_keys) < 2:
            raise RuntimeError(
                "LLM_API_KEYS must contain at least 2 comma-separated keys"
            )


# Module-level singleton — rebuilt by tests via monkeypatch.
settings = Settings()
