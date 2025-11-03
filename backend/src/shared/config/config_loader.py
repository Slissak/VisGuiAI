"""
Configuration Loader
Centralized loader for YAML configuration files (pricing, user settings, etc.)
"""
from pathlib import Path
from typing import Dict, Any
import yaml

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigLoader:
    """Centralized configuration loader for easy-to-modify YAML configs."""

    def __init__(self, config_dir_path: Path = None):
        # Path to config directory (backend/config by default)
        if config_dir_path:
            self.config_dir = config_dir_path
        else:
            # Go up from src/shared/config to backend, then to config
            self.config_dir = Path(__file__).parent.parent.parent.parent / "config"

        self._cache = {}
        logger.info(f"ConfigLoader initialized with config_dir: {self.config_dir}")

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """Load a YAML file from config directory with caching."""
        if filename in self._cache:
            return self._cache[filename]

        file_path = self.config_dir / filename
        if not file_path.exists():
            logger.warning(f"Config file not found: {filename} at {file_path}")
            return {}

        try:
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)
                self._cache[filename] = data
                logger.info(f"Loaded config: {filename}")
                return data
        except Exception as e:
            logger.error(f"Failed to load config {filename}: {e}")
            return {}

    def reload(self):
        """Clear cache to force reload of configs."""
        self._cache.clear()
        logger.info("Config cache cleared")

    # ===== PRICING =====
    def get_pricing_data(self) -> Dict[str, Any]:
        """Get model pricing data."""
        data = self._load_yaml("pricing.yaml")
        return data.get("models", {})

    # ===== USER SETTINGS =====
    def get_user_settings(self) -> Dict[str, Any]:
        """Get user tier and quota settings."""
        return self._load_yaml("user_settings.yaml")


# Global config loader instance (singleton)
_config_loader = None


def get_config_loader() -> ConfigLoader:
    """Get global config loader instance (singleton)."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader
