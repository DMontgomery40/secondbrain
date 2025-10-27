"""Configuration management for Second Brain."""

import json
import os
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
    },
    "ocr": {
        "engine": "openai",
        "model": "gpt-5",
        "api_key_env": "OPENAI_API_KEY",
        "batch_size": 5,
        "max_retries": 3,
        "rate_limit_rpm": 50,
        "include_semantic_context": True,
        "timeout_seconds": 30,
        "buffer_enabled": False,
        "buffer_duration": 30,
        "buffer_min_size": 10,
        # DeepSeek OCR settings (MLX backend only)
        "deepseek_mode": "optimal",
        "deepseek_model": "mlx-community/DeepSeek-OCR-4bit",
        "mlx_max_tokens": 1200,
        "mlx_temperature": 0.0,
    },
    "storage": {
        "retention_days": 90,
        "compression": True,
    },
    "embeddings": {
        "enabled": True,
        # Provider: 'sbert' (SentenceTransformers) or 'openai'
        "provider": "sbert",
        # SBERT model for embeddings
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        # OpenAI embeddings model when provider='openai'
        "openai_model": "text-embedding-3-small",
        # Optional reranker using BAAI bge reranker
        "reranker_enabled": False,
        "reranker_model": "BAAI/bge-reranker-large",
    },
    "context7": {
        "api_key": os.getenv("CONTEXT7_API_KEY", "ctx7sk-44085384-6ccc-4905-9c14-a5f723022f72"),
        "enabled": True,
    },
}


class Config:
    """Configuration manager for Second Brain."""

    def __init__(self, config_path: Path | None = None):
        """Initialize configuration.
        
        Args:
            config_path: Path to configuration file. If None, uses default location.
        """
        self.config_path = config_path or self.get_default_config_path()
        self.config = self._load_config()

    @staticmethod
    def get_default_config_path() -> Path:
        """Get default configuration file path."""
        return Path.home() / "Library" / "Application Support" / "second-brain" / "config" / "settings.json"

    @staticmethod
    def get_data_dir() -> Path:
        """Get data directory path."""
        return Path.home() / "Library" / "Application Support" / "second-brain"

    @staticmethod
    def get_frames_dir() -> Path:
        """Get frames directory path."""
        return Config.get_data_dir() / "frames"

    @staticmethod
    def get_database_dir() -> Path:
        """Get database directory path."""
        return Config.get_data_dir() / "database"

    @staticmethod
    def get_embeddings_dir() -> Path:
        """Get embeddings directory path."""
        return Config.get_data_dir() / "embeddings"

    @staticmethod
    def get_logs_dir() -> Path:
        """Get logs directory path."""
        return Config.get_data_dir() / "logs"

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
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
        """Deep merge update dict into base dict."""
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
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def reset_category(self, category: str) -> None:
        """Reset a specific category to defaults.

        Args:
            category: Category name (e.g., 'capture', 'ocr')
        """
        if category in DEFAULT_CONFIG:
            self.config[category] = DEFAULT_CONFIG[category].copy()
            self.save()

    def reset_all(self) -> None:
        """Reset all settings to defaults."""
        self.config = DEFAULT_CONFIG.copy()
        self.save()

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration as nested dict."""
        return self.config.copy()

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
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
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
