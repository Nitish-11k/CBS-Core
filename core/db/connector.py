"""
Database connector module.
Manages SQLAlchemy engine instances using configurations from a YAML file.
Ensures no credentials are hardcoded and uses connection pooling.
"""
import os
import yaml
from sqlalchemy import create_engine
from typing import Dict, Any, Optional

class DBConnector:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.engines = {}
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Loads database connections from the YAML config file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
        with open(self.config_path, "r") as f:
            return yaml.safe_load(f) or {}

    def get_engine(self, db_key: str):
        """
        Returns a SQLAlchemy engine for the given database key (e.g., 'source_db', 'target_db').
        Caches the engine to allow connection pooling.
        """
        if db_key in self.engines:
            return self.engines[db_key]

        if db_key not in self.config:
            raise KeyError(f"Database configuration for '{db_key}' not found in {self.config_path}.")

        db_config = self.config[db_key]
        url = db_config.get("url")
        if not url:
            # Optionally check environment variable for url if not in config
            env_var_name = f"{db_key.upper()}_URL"
            url = os.environ.get(env_var_name)
            if not url:
                raise ValueError(f"URL not provided in config or '{env_var_name}' environment variable for {db_key}.")

        # Create engine with basic pooling arguments where appropriate.
        # SQLite doesn't use pool_size/max_overflow the same way as Postgres, so we keep it simple.
        connect_args = db_config.get("connect_args", {})
        
        # If it's sqlite, we might need check_same_thread=False if using across QThreads
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            
        engine = create_engine(url, connect_args=connect_args)
        self.engines[db_key] = engine
        return engine

    def test_connection(self, db_key: str) -> bool:
        """Tests the connection to the specified database."""
        try:
            engine = self.get_engine(db_key)
            with engine.connect() as conn:
                pass # Just connect and close
            return True
        except Exception as e:
            # We can log this instead of print in a full implementation
            import logging
            logging.getLogger(__name__).error(f"Connection failed for {db_key}: {e}")
            return False
