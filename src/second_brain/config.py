"""Configuration management for Second Brain."""

import json
from pathlib import Path
from typing import Any, Dict

# Default configuration
DEFAULT_CONFIG = {
    "capture": {
        "fps": 1,
        "format": "png",
        "quality": 85,
        "max_disk_usage_gb": 100,
        "min_free_space_gb": 10,
        # Smart capture features
        "enable_frame_diff": True,
        "similarity_threshold": 0.95,
        "enable_adaptive_fps": True,
        "idle_threshold_seconds": 30.0,
    },
    "ocr": {
        "engine": "apple",
        "model": "gpt-5",
        "api_key_env": "OPENAI_API_KEY",
        "batch_size": 5,
        "max_retries": 3,
        "rate_limit_rpm": 50,
        "include_semantic_context": True,
        "timeout_seconds": 30,
    },
    "storage": {
        "retention_days": 90,
        "compression": True,
    },
    "embeddings": {
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "dimension": 384,
        "enabled": True,
        # Optional reranker for improved search relevance
        "reranker_enabled": False,
        "reranker_model": "BAAI/bge-reranker-large",
    },
}


class Config:
    """Configuration manager for Second Brain."""

    def __init__(self, config_path: Path | None = None):

        self.config_path = config_path or self.get_default_config_path()
        self.config = self._load_config()

    @staticmethod
    def get_default_config_path() -> Path:

        return Path.home() / "Library" / "Application Support" / "second-brain" / "config" / "settings.json"

    @staticmethod
    def get_data_dir() -> Path:

        return Path.home() / "Library" / "Application Support" / "second-brain"

    @staticmethod
    def get_frames_dir() -> Path:

        return Config.get_data_dir() / "frames"

    @staticmethod
    def get_database_dir() -> Path:

        return Config.get_data_dir() / "database"

    @staticmethod
    def get_embeddings_dir() -> Path:

        return Config.get_data_dir() / "embeddings"

    @staticmethod
    def get_logs_dir() -> Path:

        return Config.get_data_dir() / "logs"

    def _load_config(self) -> Dict[str, Any]:

        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                user_config = json.load(f)
                # Merge with defaults
                config = DEFAULT_CONFIG.copy()
                self._deep_merge(config, user_config)
                return config
        else:
            # Create default config
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            return DEFAULT_CONFIG.copy()

    def _deep_merge(self, base: Dict, update: Dict) -> None:

        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key.
        
        Args:
            key: Configuration key in dot notation (e.g., 'capture.fps')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set configuration value by dot-notation key.
        
        Args:
            key: Configuration key in dot notation (e.g., 'capture.fps')
            value: Value to set
        """
        keys = key.split(".")
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def save(self) -> None:

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def get_all(self) -> Dict[str, Any]:

        return self.config.copy()

    def reset_all(self) -> None:

        self.config = DEFAULT_CONFIG.copy()
        self.save()

    def reset_category(self, category: str) -> None:

        if category in DEFAULT_CONFIG:
            self.config[category] = DEFAULT_CONFIG[category].copy()
            self.save()

    def ensure_directories(self) -> None:

        directories = [
            self.get_data_dir(),
            self.get_frames_dir(),
            self.get_database_dir(),
            self.get_embeddings_dir(),
            self.get_logs_dir(),
            self.config_path.parent,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


# Global config instance
_config: Config | None = None


def get_config() -> Config:

    global _config
    if _config is None:
        _config = Config()
    return _config
