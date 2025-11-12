"""
Configuration Management Module

Loads configuration from YAML file with environment variable substitution.
Provides a singleton Config object for application-wide access.
"""

import os
import re
from typing import Any, Dict, List
import yaml
from dotenv import load_dotenv


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing required fields."""
    pass


class Config:
    """
    Application configuration loaded from YAML with environment variable substitution.

    Usage:
        config = Config.load('config.yaml')
        db_host = config.database.host
    """

    def __init__(self, config_dict: Dict[str, Any]):
        self._config = config_dict
        self._validate()

    def __getattr__(self, name: str) -> Any:
        """Allow dot notation access to configuration."""
        if name.startswith('_'):
            return object.__getattribute__(self, name)

        if name in self._config:
            value = self._config[name]
            # Recursively wrap dictionaries for dot notation
            if isinstance(value, dict):
                return Config(value)
            return value

        raise AttributeError(f"Configuration key '{name}' not found")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with optional default."""
        try:
            return self.__getattr__(key)
        except AttributeError:
            return default

    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self._config.copy()

    def _validate(self):
        """Validate required configuration fields."""
        # Only validate at top level
        if 'microshare' in self._config:
            # Validate essential sections
            required_sections = ['microshare', 'event_hub']
            for section in required_sections:
                if section not in self._config:
                    raise ConfigurationError(f"Missing required configuration section: {section}")

    @classmethod
    def load(cls, config_path: str = 'config.yaml', env_path: str = '.env') -> 'Config':
        """
        Load configuration from YAML file with environment variable substitution.

        Args:
            config_path: Path to YAML configuration file
            env_path: Path to .env file (optional)

        Returns:
            Config object

        Raises:
            ConfigurationError: If configuration is invalid or files not found
        """
        # Load environment variables from .env file if it exists
        if os.path.exists(env_path):
            load_dotenv(env_path)

        # Check if config file exists
        if not os.path.exists(config_path):
            raise ConfigurationError(f"Configuration file not found: {config_path}")

        # Load YAML file
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)

        # Substitute environment variables
        config_dict = cls._substitute_env_vars(raw_config)

        return cls(config_dict)

    @classmethod
    def _substitute_env_vars(cls, obj: Any) -> Any:
        """
        Recursively substitute ${VAR_NAME} with environment variable values.

        Args:
            obj: Configuration object (dict, list, str, etc.)

        Returns:
            Object with substituted values
        """
        if isinstance(obj, dict):
            return {key: cls._substitute_env_vars(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [cls._substitute_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            # Match ${VAR_NAME} pattern
            pattern = r'\$\{([^}]+)\}'

            def replace_var(match):
                var_name = match.group(1)
                value = os.getenv(var_name)
                if value is None:
                    raise ConfigurationError(
                        f"Environment variable '{var_name}' not found. "
                        f"Please set it in your .env file or environment."
                    )
                return value

            return re.sub(pattern, replace_var, obj)
        else:
            return obj


# Singleton instance
_config_instance: Config = None


def get_config(config_path: str = 'config.yaml', env_path: str = '.env') -> Config:
    """
    Get singleton configuration instance.

    Args:
        config_path: Path to YAML configuration file
        env_path: Path to .env file

    Returns:
        Config singleton instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config.load(config_path, env_path)
    return _config_instance


def reload_config(config_path: str = 'config.yaml', env_path: str = '.env') -> Config:
    """
    Force reload configuration (useful for testing).

    Args:
        config_path: Path to YAML configuration file
        env_path: Path to .env file

    Returns:
        New Config instance
    """
    global _config_instance
    _config_instance = Config.load(config_path, env_path)
    return _config_instance
