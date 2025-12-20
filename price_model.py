import requests
import logging

logger = logging.getLogger(__name__)

class PriceModel:
    # World Boundaries
    X1, X2 = -5176, 5176
    Z1, Z2 = -2488, 2488
    
    # Market to Item ID mapping (Beta 1.7.3)
    # Based on standard IDs. Metric keys are strings.
    MARKET_MAPPING = {
        "ston_iron": ["1", "4"], # Stone, Cobble
        "olog_iron": ["17", "17:0", "17:1", "17:2"], # Logs (Oak, Spruce, Birch) - wait, metrics might separate them.
        # Actually standard ID 17 is Log. Data values: 0=Oak, 1=Spruce, 2=Birch.
        # If metrics separates them, we need to map individually.
        # Let's assume metrics might have distinct IDs or data values.
        # Adding explicit keys for clarity if the market names exist.
        "slog_iron": ["17:1"], # Spruce Log
        "blog_iron": ["17:2"], # Birch Log
        "diam_iron": ["264", "56", "57"], # Diamond, Ore, Block
        "gold_iron": ["266", "14", "41"], # Gold Ingot, Ore, Block
        "coal_iron": ["263", "263:1", "16"], # Coal, Charcoal, Ore
        "cobl_iron": ["4"], # Cobblestone
        "sand_iron": ["12"], # Sand
        "wool_iron": ["35"], # Wool (all colors? metrics usually splits 35:x)
        "whet_iron": ["296", "295"], # Wheat, Seeds
        "sugr_iron": ["338", "262"], # Reeds, Sugar (approx)
        "clay_iron": ["337", "82"], # Clay Ball, Clay Block
        "slme_iron": ["341"], # Slimeball
        "gpow_iron": ["289"], # Gunpowder
        "xtnt_iron": ["46"], # TNT
        "lapi_iron": ["351:4", "21"], # Lapis Dye, Ore
        "aapl_iron": ["260"], # Apple
        "beef_iron": ["363", "364"], # Raw/Cooked Beef - Note: Not in vanilla Beta 1.7.3 but server supports it (custom/modded)
        "bmus_iron": ["39"], # Brown Mushroom
        "rmus_iron": ["40"], # Red Mushroom
        "dand_iron": ["37"], # Dandelion
        "dirt_iron": ["3"], # Dirt
        "fish_iron": ["349", "350"], # Fish
        "flnt_iron": ["318"], # Flint
        "fthr_iron": ["288"], # Feather
        "popy_iron": ["38"], # Rose
        "snow_iron": ["332", "78"], # Snowball, Layer
        "stng_iron": ["287"], # String
        "grvl_iron": ["13"], # Gravel
        "bone_iron": ["352"], # Bone
        "reds_iron": ["331", "73"], # Redstone dust, Ore
        "obsn_iron": ["49"], # Obsidian
        "cact_iron": ["81"], # Cactus
        "arrw_iron": ["262"], # Arrow
        "pump_iron": ["86"], # Pumpkin
        "eggs_iron": ["344"], # Egg
    }

    # Default Base "Intrinsic" Value (Price when 0% acquired)
    # Rare items higher, common lower.
    # These can be overridden via config.yaml
    DEFAULT_BASE_PRICES = {
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
    }

    def __init__(self, client, base_prices: dict = None):
        """
        Initialize PriceModel.
        
        Args:
            client: Blocky API client for fetching supply metrics.
            base_prices: Optional dict of market -> base price. Merged with defaults.
        """
        self.client = client
        self.endpoint = client.BASE_URL
        self.total_chunks = self._calculate_chunks()
        
        # Merge provided base_prices with defaults (config overrides defaults)
        self.base_prices = self.DEFAULT_BASE_PRICES.copy()
        if base_prices:
            self.base_prices.update(base_prices)
            logger.info(f"Price model: Using {len(base_prices)} custom base prices from config")
        
        # Cache for metrics
        self._metrics_cache = None
        self._metrics_cache_time = 0
        self._cache_ttl = 60 # Seconds
        self._stale_threshold = 300  # 5 minutes - warn if cache older than this
        self._using_stale_cache = False
        self._consecutive_failures = 0
        
        # Initialize estimates for all keys in mapping
        self.world_supply = {}
        for market in self.MARKET_MAPPING:
             self.world_supply[market] = self._estimate_supply(market)
             
        logger.info(f"Total Chunks: {self.total_chunks}")
        
    def _estimate_supply(self, market: str) -> int:
        # Crude estimates based on generation per chunk
        if "diam" in market: return self.total_chunks * 3 # Very rare
        if "gold" in market: return self.total_chunks * 8
        if "lapi" in market: return self.total_chunks * 3 # (Multi-drop)
        if "coal" in market: return self.total_chunks * 140
        if "iron" in market and "iron_iron" not in market: return self.total_chunks * 70 # Iron Ore
        if "reds" in market: return self.total_chunks * 25 # (Multi-drop)
        if "ston" in market or "cobl" in market: return self.total_chunks * 20000
        if "dirt" in market: return self.total_chunks * 3000
        if "sand" in market: return self.total_chunks * 2000 # Deserts/Beaches
        if "olog" in market: return self.total_chunks * 40
        if "obsn" in market: return self.total_chunks * 0.5 # Deep caves/lava
        if "clay" in market: return self.total_chunks * 20
        return self.total_chunks * 100 # Default fallback

    def _calculate_chunks(self) -> int:
        width = abs(self.X2 - self.X1)
        depth = abs(self.Z2 - self.Z1)
        total_blocks_area = width * depth
        return int(total_blocks_area / 256)

    def get_circulating_supply(self) -> dict:
        import time
        current_time = time.time()
        
        # Return cache if valid
        if self._metrics_cache and (current_time - self._metrics_cache_time < self._cache_ttl):
            return self._metrics_cache
        
        # Check for stale cache and warn
        cache_age = current_time - self._metrics_cache_time if self._metrics_cache_time > 0 else 0
        if cache_age > self._stale_threshold and self._metrics_cache:
            logger.warning(f"⚠️ Metrics cache is stale ({cache_age:.0f}s old). Using cached data.")
            self._using_stale_cache = True
        else:
            self._using_stale_cache = False
            
        try:
            # Use shared client optimized connection pool
            data = self.client.get_supply_metrics(time_range="24h", interval="1h")
            
            if not data or not isinstance(data, list):
                self._consecutive_failures += 1
                if self._consecutive_failures >= 3:
                    logger.error(f"🚨 Metrics API returned invalid data {self._consecutive_failures} times consecutively!")
                return self._metrics_cache or {}

            # Get latest data point
            latest = data[-1]
            
            supplies = {}
            for market, ids in self.MARKET_MAPPING.items():
                total = 0
                for item_id in ids:
                    total += latest.get(item_id, 0)
                supplies[market] = total
            
            # Update cache and reset failure counter
            self._metrics_cache = supplies
            self._metrics_cache_time = current_time
            self._consecutive_failures = 0
            self._using_stale_cache = False
            logger.info("Metrics cache updated.")
            
            return supplies
        except Exception as e:
            self._consecutive_failures += 1
            if self._consecutive_failures >= 3:
                logger.error(f"🚨 Metrics API failing consistently: {e} (failure #{self._consecutive_failures})")
            else:
                logger.warning(f"Error fetching metrics: {e}")
            return self._metrics_cache or {} # Return stale cache if available
    
    def is_healthy(self) -> bool:
        """Returns True if metrics data is fresh and reliable."""
        return not self._using_stale_cache and self._consecutive_failures < 3

    def calculate_fair_price(self, market: str) -> float:
        supplies = self.get_circulating_supply()
        circulating = supplies.get(market, 0)
        total_possible = self.world_supply.get(market, 1)
        
        # If we have no mapping, we can't calculate scarcity.
        # Fallback to a default Base Price or 0 (to let bot skip or use ticker).
        if market not in self.MARKET_MAPPING:
             logger.warning(f"No mapping for {market}. Using default.")
             return 0.0

        remaining = total_possible - circulating
        if remaining <= 0:
            remaining = 1 # Prevent div by zero
            
        multiplier = total_possible / remaining
        
        # Base price fallback (using instance prices which include config overrides)
        base = self.base_prices.get(market, 1.0) # Default 1.0 if unknown
        
        fair_price = base * multiplier
        
        # Cap multiplier to prevent extreme prices if we underestimated Total
        # e.g. if we said 10 diamonds total and found 11, remaining is -1 (handled above), price implies infinite.
        if multiplier > 20: 
             fair_price = base * 20
        
        return fair_price
