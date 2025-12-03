"""
Application settings and configuration.

Uses environment variables with sensible defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import os
from typing import Optional


@dataclass
class XAPISettings:
    """X/Twitter API configuration."""
    bearer_token: str = ""
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    access_token_secret: str = ""

    # Rate limiting
    max_requests_per_15min: int = 450
    stream_reconnect_delay_seconds: int = 30

    # Filtering
    min_follower_count: int = 100  # Ignore accounts with fewer followers
    exclude_bots: bool = True
    languages: list[str] = field(default_factory=lambda: ["en"])

    @classmethod
    def from_env(cls) -> XAPISettings:
        """Load from environment variables."""
        return cls(
            bearer_token=os.getenv("X_BEARER_TOKEN", ""),
            api_key=os.getenv("X_API_KEY", ""),
            api_secret=os.getenv("X_API_SECRET", ""),
            access_token=os.getenv("X_ACCESS_TOKEN", ""),
            access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET", ""),
        )


@dataclass
class MarketDataSettings:
    """Market data API configuration."""
    provider: str = "polygon"  # "polygon", "alphavantage", "yahoo"
    api_key: str = ""

    # Polling
    poll_interval_seconds: int = 60
    pre_market_enabled: bool = True
    after_hours_enabled: bool = True

    @classmethod
    def from_env(cls) -> MarketDataSettings:
        """Load from environment variables."""
        return cls(
            provider=os.getenv("MARKET_DATA_PROVIDER", "polygon"),
            api_key=os.getenv("MARKET_DATA_API_KEY", ""),
        )


@dataclass
class LLMSettings:
    """LLM API configuration."""
    provider: str = "anthropic"  # "anthropic", "openai"
    model: str = "claude-sonnet-4-20250514"
    api_key: str = ""

    # Rate limiting
    max_requests_per_minute: int = 50
    max_tokens_per_request: int = 4096

    # Embeddings
    embedding_model: str = "text-embedding-ada-002"
    embedding_dimensions: int = 1536

    @classmethod
    def from_env(cls) -> LLMSettings:
        """Load from environment variables."""
        return cls(
            provider=os.getenv("LLM_PROVIDER", "anthropic"),
            model=os.getenv("LLM_MODEL", "claude-sonnet-4-20250514"),
            api_key=os.getenv("ANTHROPIC_API_KEY", os.getenv("OPENAI_API_KEY", "")),
        )


@dataclass
class DatabaseSettings:
    """Database configuration."""
    # TimescaleDB (time-series)
    timescale_host: str = "localhost"
    timescale_port: int = 5432
    timescale_database: str = "mypersona"
    timescale_user: str = "postgres"
    timescale_password: str = ""

    # Neo4j (graph)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # Redis (cache and queues)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""

    # Vector store
    vector_store: str = "pinecone"  # "pinecone", "weaviate", "local"
    pinecone_api_key: str = ""
    pinecone_environment: str = ""
    pinecone_index: str = "mypersona-embeddings"

    @classmethod
    def from_env(cls) -> DatabaseSettings:
        """Load from environment variables."""
        return cls(
            timescale_host=os.getenv("TIMESCALE_HOST", "localhost"),
            timescale_port=int(os.getenv("TIMESCALE_PORT", "5432")),
            timescale_database=os.getenv("TIMESCALE_DATABASE", "mypersona"),
            timescale_user=os.getenv("TIMESCALE_USER", "postgres"),
            timescale_password=os.getenv("TIMESCALE_PASSWORD", ""),
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_password=os.getenv("REDIS_PASSWORD", ""),
            vector_store=os.getenv("VECTOR_STORE", "pinecone"),
            pinecone_api_key=os.getenv("PINECONE_API_KEY", ""),
            pinecone_environment=os.getenv("PINECONE_ENVIRONMENT", ""),
            pinecone_index=os.getenv("PINECONE_INDEX", "mypersona-embeddings"),
        )

    @property
    def timescale_dsn(self) -> str:
        """Get TimescaleDB connection string."""
        return (
            f"postgresql://{self.timescale_user}:{self.timescale_password}"
            f"@{self.timescale_host}:{self.timescale_port}/{self.timescale_database}"
        )

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}"
        return f"redis://{self.redis_host}:{self.redis_port}"


@dataclass
class DetectionSettings:
    """Delta detection configuration."""
    # Time windows
    snapshot_window_minutes: int = 15
    baseline_lookback_days: int = 30

    # Thresholds
    topic_absence_threshold: float = 0.3  # < 30% of expected = absence
    voice_silence_threshold_hours: float = 24.0  # Silent for 24h = unusual
    sentiment_deviation_threshold: float = 2.0  # Z-score threshold
    volume_collapse_threshold: float = 0.5  # < 50% of expected

    # Confidence thresholds
    min_delta_confidence: float = 0.5  # Ignore deltas below this
    min_event_confidence: float = 0.6  # Ignore events below this

    # Clustering
    delta_cluster_window_minutes: int = 60
    min_cluster_size: int = 2

    @classmethod
    def from_env(cls) -> DetectionSettings:
        """Load from environment variables."""
        return cls(
            snapshot_window_minutes=int(os.getenv("SNAPSHOT_WINDOW_MINUTES", "15")),
            baseline_lookback_days=int(os.getenv("BASELINE_LOOKBACK_DAYS", "30")),
            min_delta_confidence=float(os.getenv("MIN_DELTA_CONFIDENCE", "0.5")),
            min_event_confidence=float(os.getenv("MIN_EVENT_CONFIDENCE", "0.6")),
        )


@dataclass
class TrackedEntity:
    """Configuration for an entity being tracked."""
    entity_id: str
    name: str
    entity_type: str  # "company", "person", "topic"

    # Associated identifiers
    tickers: list[str] = field(default_factory=list)
    usernames: list[str] = field(default_factory=list)  # Official X accounts
    keywords: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)

    # Key voices to track
    key_voices: list[str] = field(default_factory=list)  # Account IDs

    # Priority (higher = more resources)
    priority: int = 1

    # Enabled
    enabled: bool = True


@dataclass
class Settings:
    """Complete application settings."""
    # Environment
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # API keys and external services
    x_api: XAPISettings = field(default_factory=XAPISettings.from_env)
    market_data: MarketDataSettings = field(default_factory=MarketDataSettings.from_env)
    llm: LLMSettings = field(default_factory=LLMSettings.from_env)
    database: DatabaseSettings = field(default_factory=DatabaseSettings.from_env)

    # Detection settings
    detection: DetectionSettings = field(default_factory=DetectionSettings.from_env)

    # Tracked entities
    tracked_entities: list[TrackedEntity] = field(default_factory=list)

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @classmethod
    def from_env(cls) -> Settings:
        """Load all settings from environment."""
        return cls(
            environment=os.getenv("ENVIRONMENT", "development"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            x_api=XAPISettings.from_env(),
            market_data=MarketDataSettings.from_env(),
            llm=LLMSettings.from_env(),
            database=DatabaseSettings.from_env(),
            detection=DetectionSettings.from_env(),
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8000")),
        )

    def add_tracked_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        tickers: Optional[list[str]] = None,
        usernames: Optional[list[str]] = None,
        keywords: Optional[list[str]] = None,
    ) -> None:
        """Add an entity to track."""
        self.tracked_entities.append(
            TrackedEntity(
                entity_id=entity_id,
                name=name,
                entity_type=entity_type,
                tickers=tickers or [],
                usernames=usernames or [],
                keywords=keywords or [],
            )
        )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings.from_env()
