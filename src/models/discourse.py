"""
Discourse models representing the current state of social platform activity.

These models capture "what IS being said" - the observed reality of discourse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import hashlib


class PostType(Enum):
    """Type of social media post."""
    ORIGINAL = "original"
    REPLY = "reply"
    REPOST = "repost"
    QUOTE = "quote"


class AccountType(Enum):
    """Classification of account type for weighted analysis."""
    INDIVIDUAL = "individual"
    COMPANY_OFFICIAL = "company_official"
    EXECUTIVE = "executive"
    MEDIA = "media"
    ANALYST = "analyst"
    INFLUENCER = "influencer"
    BOT_SUSPECTED = "bot_suspected"
    UNKNOWN = "unknown"


@dataclass
class Account:
    """
    Represents a social media account.

    Tracks both identity and behavioral patterns for expectation modeling.
    """
    platform_id: str
    username: str
    display_name: str

    # Classification
    account_type: AccountType = AccountType.UNKNOWN
    verified: bool = False
    follower_count: int = 0

    # Behavioral baseline (populated from historical analysis)
    avg_posts_per_day: float = 0.0
    avg_sentiment: float = 0.0  # -1 to 1
    typical_topics: list[str] = field(default_factory=list)
    typical_active_hours: list[int] = field(default_factory=list)  # 0-23 UTC
    typical_response_accounts: list[str] = field(default_factory=list)

    # Influence scoring
    influence_score: float = 0.0  # Computed based on reach, engagement, authority

    # Metadata
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    @property
    def account_id(self) -> str:
        """Unique identifier combining platform and ID."""
        return f"x:{self.platform_id}"

    def is_high_value(self) -> bool:
        """Determine if this account's silence would be significant."""
        return (
            self.account_type in [
                AccountType.EXECUTIVE,
                AccountType.COMPANY_OFFICIAL,
                AccountType.ANALYST,
            ]
            or self.influence_score > 0.7
            or self.verified
        )


@dataclass
class Topic:
    """
    Represents a topic/theme extracted from discourse.

    Topics can be entities (companies, people), concepts, events, or sentiments.
    """
    topic_id: str
    name: str

    # Topic classification
    topic_type: str  # "entity", "concept", "event", "ticker", "hashtag"

    # Related identifiers
    tickers: list[str] = field(default_factory=list)  # e.g., ["TSLA", "TWTR"]
    entities: list[str] = field(default_factory=list)  # Named entities
    hashtags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    # Semantic embedding for similarity matching
    embedding: Optional[list[float]] = None

    # Baseline metrics
    avg_daily_mentions: float = 0.0
    avg_sentiment: float = 0.0
    typical_discussants: list[str] = field(default_factory=list)  # Account IDs

    @classmethod
    def from_ticker(cls, ticker: str) -> Topic:
        """Create a topic from a stock ticker."""
        return cls(
            topic_id=f"ticker:{ticker.upper()}",
            name=ticker.upper(),
            topic_type="ticker",
            tickers=[ticker.upper()],
        )

    @classmethod
    def from_hashtag(cls, hashtag: str) -> Topic:
        """Create a topic from a hashtag."""
        clean_tag = hashtag.lstrip("#").lower()
        return cls(
            topic_id=f"hashtag:{clean_tag}",
            name=f"#{clean_tag}",
            topic_type="hashtag",
            hashtags=[clean_tag],
        )


@dataclass
class Post:
    """
    Represents a single social media post.

    The atomic unit of discourse - contains the raw content and extracted features.
    """
    post_id: str
    platform: str  # "x", "reddit", etc.

    # Content
    text: str
    created_at: datetime

    # Author
    author: Account

    # Post metadata
    post_type: PostType = PostType.ORIGINAL
    reply_to_id: Optional[str] = None
    quote_of_id: Optional[str] = None

    # Engagement metrics
    likes: int = 0
    reposts: int = 0
    replies: int = 0
    views: int = 0

    # Extracted features (populated by preprocessor)
    topics: list[Topic] = field(default_factory=list)
    mentioned_accounts: list[str] = field(default_factory=list)
    sentiment_score: float = 0.0  # -1 (negative) to 1 (positive)
    tone_markers: list[str] = field(default_factory=list)  # "urgent", "defensive", etc.

    # Language features
    language: str = "en"
    contains_media: bool = False
    contains_link: bool = False

    # Processing metadata
    processed_at: Optional[datetime] = None
    embedding: Optional[list[float]] = None

    @property
    def unique_id(self) -> str:
        """Platform-qualified unique identifier."""
        return f"{self.platform}:{self.post_id}"

    @property
    def engagement_score(self) -> float:
        """Normalized engagement metric."""
        # Weighted engagement calculation
        raw_score = (
            self.likes * 1.0 +
            self.reposts * 2.0 +
            self.replies * 3.0  # Replies indicate conversation
        )
        # Normalize by views if available
        if self.views > 0:
            return raw_score / self.views
        return raw_score

    def content_hash(self) -> str:
        """Hash of content for deduplication."""
        return hashlib.md5(self.text.encode()).hexdigest()


@dataclass
class ConversationThread:
    """
    Represents a conversation thread (post + replies).

    Important for detecting broken response patterns and missing voices.
    """
    thread_id: str
    root_post: Post
    replies: list[Post] = field(default_factory=list)

    # Participants in the thread
    participants: list[Account] = field(default_factory=list)

    # Thread metrics
    depth: int = 0  # Maximum reply depth
    duration_minutes: int = 0  # Time from first to last post

    # Expected but missing participants
    expected_responders: list[Account] = field(default_factory=list)
    actual_responders: list[Account] = field(default_factory=list)

    @property
    def missing_responders(self) -> list[Account]:
        """Accounts expected to respond but didn't."""
        expected_ids = {a.account_id for a in self.expected_responders}
        actual_ids = {a.account_id for a in self.actual_responders}
        missing_ids = expected_ids - actual_ids
        return [a for a in self.expected_responders if a.account_id in missing_ids]


@dataclass
class DiscourseSnapshot:
    """
    A point-in-time capture of discourse state.

    This represents "what IS being said" at a specific moment for a specific
    entity or topic. Used for comparison against expectations.
    """
    snapshot_id: str
    entity: str  # What entity/topic this snapshot covers

    # Time window
    window_start: datetime
    window_end: datetime

    # Aggregated content
    posts: list[Post] = field(default_factory=list)
    threads: list[ConversationThread] = field(default_factory=list)

    # Aggregated metrics
    total_posts: int = 0
    unique_authors: int = 0
    total_engagement: int = 0

    # Topic distribution
    topic_counts: dict[str, int] = field(default_factory=dict)
    topic_sentiments: dict[str, float] = field(default_factory=dict)

    # Voice distribution
    active_accounts: list[Account] = field(default_factory=list)
    high_value_accounts_active: list[Account] = field(default_factory=list)

    # Computed features
    avg_sentiment: float = 0.0
    sentiment_variance: float = 0.0
    volume_vs_baseline: float = 1.0  # 1.0 = normal, 2.0 = double normal

    # Tone analysis
    dominant_tones: list[str] = field(default_factory=list)
    tone_shift_detected: bool = False

    @property
    def duration_minutes(self) -> int:
        """Duration of the snapshot window in minutes."""
        delta = self.window_end - self.window_start
        return int(delta.total_seconds() / 60)

    def get_topic_volume(self, topic_id: str) -> int:
        """Get mention count for a specific topic."""
        return self.topic_counts.get(topic_id, 0)

    def get_topic_sentiment(self, topic_id: str) -> Optional[float]:
        """Get average sentiment for a specific topic."""
        return self.topic_sentiments.get(topic_id)
