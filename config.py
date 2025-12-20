"""
Configuration loader for the Market Maker bot.
Supports YAML config file with environment variable overrides.
"""
import os
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Try to import PyYAML, fall back to built-in config if not available
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    logger.warning("PyYAML not installed. Using default configuration only.")


@dataclass
class APIConfig:
    endpoint: str = "https://craft.blocky.com.br/api/v1"
    api_key: Optional[str] = None


@dataclass 
class TradingConfig:
    dry_run: bool = False  # If True, log orders but don't execute
    enabled_markets: List[str] = field(default_factory=list)  # Whitelist (empty = all)
    disabled_markets: List[str] = field(default_factory=list)  # Blacklist (overrides enabled)
    spread: float = 0.05
    min_spread_ticks: float = 0.01
    target_value: float = 10.0
    max_quantity: int = 6400
    refresh_interval: int = 60


@dataclass
class RateLimitConfig:
    max_requests: int = 30
    window_seconds: float = 1.0


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3


@dataclass
class MetricsConfig:
    persistence_path: str = "metrics_data.json"
    auto_save_interval: int = 60


@dataclass
class AlertsConfig:
    enabled: bool = True
    webhook_url: Optional[str] = None
    webhook_type: str = "discord"
    min_level: str = "warning"
    rate_limit_seconds: float = 60.0


@dataclass
class LoggingConfig:
    level: str = "INFO"
    colored_output: bool = True


@dataclass
class PriceModelConfig:
    cache_ttl: int = 60
    base_prices: Dict[str, float] = field(default_factory=lambda: {
        "diam_iron": 50.0,
        "gold_iron": 5.0,
        "lapi_iron": 2.0,
        "coal_iron": 0.5,
        "ston_iron": 0.1,
        "cobl_iron": 0.05,
        "dirt_iron": 0.01,
        "sand_iron": 0.05,
        "olog_iron": 0.45,
        "obsn_iron": 2.5,
        "slme_iron": 5.0,
    })


@dataclass
class DynamicSpreadConfig:
    """Configuration for dynamic spread calculation."""
    enabled: bool = True
    base_spread: float = 0.03           # 3% base spread
    volatility_multiplier: float = 2.0  # How much volatility affects spread
    inventory_impact: float = 0.02      # Max adjustment from inventory imbalance
    min_spread: float = 0.01            # 1% minimum spread
    max_spread: float = 0.15            # 15% maximum spread
    volatility_window: int = 24         # Hours of OHLCV data


@dataclass
class HealthConfig:
    """Configuration for health endpoint."""
    enabled: bool = True
    port: int = 8080


@dataclass
class Config:
    """Main configuration container."""
    api: APIConfig = field(default_factory=APIConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    alerts: AlertsConfig = field(default_factory=AlertsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    price_model: PriceModelConfig = field(default_factory=PriceModelConfig)
    dynamic_spread: DynamicSpreadConfig = field(default_factory=DynamicSpreadConfig)
    health: HealthConfig = field(default_factory=HealthConfig)


def _deep_update(base: dict, updates: dict) -> dict:
    """Recursively update a dict with another dict."""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def load_config(config_path: str = "config.yaml") -> Config:
    """
    Load configuration from YAML file with environment variable overrides.
    
    Priority (highest to lowest):
    1. Environment variables
    2. config.yaml file
    3. Default values
    
    Environment variable mapping:
    - BLOCKY_API_KEY -> api.api_key
    - BLOCKY_API_ENDPOINT -> api.endpoint
    - ALERT_WEBHOOK_URL -> alerts.webhook_url
    - ALERT_WEBHOOK_TYPE -> alerts.webhook_type
    - LOG_LEVEL -> logging.level
    """
    config = Config()
    
    # Load from YAML file if available
    if YAML_AVAILABLE and os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                yaml_config = yaml.safe_load(f) or {}
            
            # Apply YAML values to config
            if 'api' in yaml_config:
                for key, value in yaml_config['api'].items():
                    if hasattr(config.api, key):
                        setattr(config.api, key, value)
            
            if 'trading' in yaml_config:
                for key, value in yaml_config['trading'].items():
                    if hasattr(config.trading, key):
                        setattr(config.trading, key, value)
            
            if 'rate_limit' in yaml_config:
                for key, value in yaml_config['rate_limit'].items():
                    if hasattr(config.rate_limit, key):
                        setattr(config.rate_limit, key, value)
            
            if 'circuit_breaker' in yaml_config:
                for key, value in yaml_config['circuit_breaker'].items():
                    if hasattr(config.circuit_breaker, key):
                        setattr(config.circuit_breaker, key, value)
            
            if 'metrics' in yaml_config:
                for key, value in yaml_config['metrics'].items():
                    if hasattr(config.metrics, key):
                        setattr(config.metrics, key, value)
            
            if 'alerts' in yaml_config:
                for key, value in yaml_config['alerts'].items():
                    if hasattr(config.alerts, key):
                        setattr(config.alerts, key, value)
            
            if 'logging' in yaml_config:
                for key, value in yaml_config['logging'].items():
                    if hasattr(config.logging, key):
                        setattr(config.logging, key, value)
            
            if 'price_model' in yaml_config:
                if 'cache_ttl' in yaml_config['price_model']:
                    config.price_model.cache_ttl = yaml_config['price_model']['cache_ttl']
                if 'base_prices' in yaml_config['price_model']:
                    config.price_model.base_prices.update(yaml_config['price_model']['base_prices'])
            
            if 'dynamic_spread' in yaml_config:
                for key, value in yaml_config['dynamic_spread'].items():
                    if hasattr(config.dynamic_spread, key):
                        setattr(config.dynamic_spread, key, value)
            
            if 'health' in yaml_config:
                for key, value in yaml_config['health'].items():
                    if hasattr(config.health, key):
                        setattr(config.health, key, value)
            
            logger.info(f"📄 Loaded configuration from {config_path}")
            
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
    
    # Apply environment variable overrides
    if os.environ.get("BLOCKY_API_KEY"):
        config.api.api_key = os.environ["BLOCKY_API_KEY"]
    
    if os.environ.get("BLOCKY_API_ENDPOINT"):
        config.api.endpoint = os.environ["BLOCKY_API_ENDPOINT"]
    
    if os.environ.get("ALERT_WEBHOOK_URL"):
        config.alerts.webhook_url = os.environ["ALERT_WEBHOOK_URL"]
    
    if os.environ.get("ALERT_WEBHOOK_TYPE"):
        config.alerts.webhook_type = os.environ["ALERT_WEBHOOK_TYPE"]
    
    if os.environ.get("LOG_LEVEL"):
        config.logging.level = os.environ["LOG_LEVEL"]
    
    return config


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or load the global configuration."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
