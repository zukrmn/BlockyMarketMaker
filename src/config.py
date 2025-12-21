"""
Configuration loader for the Market Maker bot using Pydantic v2.
Supports YAML config file with environment variable overrides.
"""
import os
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# Try to import PyYAML
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    logger.warning("PyYAML not installed. Using default configuration only.")


class APIConfig(BaseModel):
    """API connection configuration."""
    endpoint: str = "https://craft.blocky.com.br/api/v1"
    api_key: Optional[str] = None


class TradingConfig(BaseModel):
    """Trading parameters configuration."""
    dry_run: bool = False
    enabled_markets: List[str] = Field(default_factory=list)
    disabled_markets: List[str] = Field(default_factory=list)
    spread: float = 0.05
    min_spread_ticks: float = 0.01
    target_value: float = 10.0
    max_quantity: int = 6400
    refresh_interval: int = 60


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    max_requests: int = 30
    window_seconds: float = 1.0


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3


class MetricsConfig(BaseModel):
    """Metrics persistence configuration."""
    persistence_path: str = "metrics_data.json"
    auto_save_interval: int = 60


class AlertsConfig(BaseModel):
    """Alert system configuration."""
    enabled: bool = True
    webhook_url: Optional[str] = None
    webhook_type: str = "discord"
    min_level: str = "warning"
    rate_limit_seconds: float = 60.0


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    colored_output: bool = True


class PriceModelConfig(BaseModel):
    """Price model configuration."""
    cache_ttl: int = 60
    base_prices: Dict[str, float] = Field(default_factory=lambda: {
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


class DynamicSpreadConfig(BaseModel):
    """Dynamic spread calculation configuration."""
    enabled: bool = True
    base_spread: float = 0.03
    volatility_multiplier: float = 2.0
    inventory_impact: float = 0.02
    min_spread: float = 0.01
    max_spread: float = 0.15
    volatility_window: int = 24


class HealthConfig(BaseModel):
    """Health endpoint configuration."""
    enabled: bool = True
    port: int = 8080


class StrategyConfig(BaseModel):
    """Strategy selection configuration."""
    type: str = "composite"  # scarcity, ticker, vwap, composite


class Config(BaseSettings):
    """
    Main configuration container with environment variable support.
    
    Environment variables override YAML values:
    - BLOCKY_API_KEY -> api.api_key
    - BLOCKY_API_ENDPOINT -> api.endpoint
    - ALERT_WEBHOOK_URL -> alerts.webhook_url
    - ALERT_WEBHOOK_TYPE -> alerts.webhook_type
    - LOG_LEVEL -> logging.level
    """
    api: APIConfig = Field(default_factory=APIConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    price_model: PriceModelConfig = Field(default_factory=PriceModelConfig)
    dynamic_spread: DynamicSpreadConfig = Field(default_factory=DynamicSpreadConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)

    model_config = {
        "extra": "ignore"
    }


def load_config(config_path: str = "config.yaml") -> Config:
    """
    Load configuration from YAML file with environment variable overrides.
    
    Priority (highest to lowest):
    1. Environment variables
    2. config.yaml file
    3. Default values
    """
    config_dict = {}
    
    # Load from YAML file if available
    if YAML_AVAILABLE and os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                yaml_config = yaml.safe_load(f) or {}
            config_dict = yaml_config
            logger.info(f"📄 Loaded configuration from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
    
    # Create config from YAML dict
    config = Config(**config_dict)
    
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
