"""
Preprocessor for cleaning and extracting features from posts.

Handles:
- Text normalization
- Entity extraction
- Sentiment analysis
- Tone detection
- Embedding generation
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import logging

from ..models.discourse import Post, Topic, Account

logger = logging.getLogger(__name__)


# Regex patterns for extraction
TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b')
HASHTAG_PATTERN = re.compile(r'#(\w+)')
MENTION_PATTERN = re.compile(r'@(\w+)')
URL_PATTERN = re.compile(r'https?://\S+')
CASHTAG_PATTERN = re.compile(r'\$([A-Z]{1,5})')


@dataclass
class SentimentResult:
    """Result of sentiment analysis."""
    score: float  # -1 to 1
    confidence: float  # 0 to 1
    tones: list[str]  # e.g., ["urgent", "defensive", "optimistic"]


class Preprocessor:
    """
    Preprocesses posts for analysis.

    Extracts entities, calculates sentiment, generates embeddings.
    """

    def __init__(
        self,
        sentiment_analyzer: Optional[SentimentAnalyzer] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
    ):
        self.sentiment_analyzer = sentiment_analyzer or SimpleSentimentAnalyzer()
        self.embedding_generator = embedding_generator

    async def process(self, post: Post) -> Post:
        """
        Process a post and extract features.

        Returns the same Post object with extracted features populated.
        """
        # Extract entities
        post.topics = self._extract_topics(post.text)
        post.mentioned_accounts = self._extract_mentions(post.text)
        post.contains_link = bool(URL_PATTERN.search(post.text))
        post.contains_media = self._detect_media(post.text)

        # Analyze sentiment
        sentiment = await self.sentiment_analyzer.analyze(post.text)
        post.sentiment_score = sentiment.score
        post.tone_markers = sentiment.tones

        # Generate embedding if available
        if self.embedding_generator:
            post.embedding = await self.embedding_generator.generate(post.text)

        post.processed_at = datetime.utcnow()

        return post

    def _extract_topics(self, text: str) -> list[Topic]:
        """Extract topics from text."""
        topics = []

        # Extract tickers
        tickers = TICKER_PATTERN.findall(text)
        for ticker in set(tickers):
            topics.append(Topic.from_ticker(ticker))

        # Extract hashtags
        hashtags = HASHTAG_PATTERN.findall(text)
        for hashtag in set(hashtags):
            topics.append(Topic.from_hashtag(hashtag))

        return topics

    def _extract_mentions(self, text: str) -> list[str]:
        """Extract mentioned usernames."""
        mentions = MENTION_PATTERN.findall(text)
        return list(set(mentions))

    def _detect_media(self, text: str) -> bool:
        """Detect if post likely contains media."""
        # Check for media-related URLs or indicators
        media_indicators = [
            "pic.twitter.com",
            "video",
            "photo",
            ".jpg",
            ".png",
            ".gif",
            ".mp4",
        ]
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in media_indicators)


class SentimentAnalyzer:
    """Base class for sentiment analysis."""

    async def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment of text."""
        raise NotImplementedError


class SimpleSentimentAnalyzer(SentimentAnalyzer):
    """
    Simple rule-based sentiment analyzer.

    For production, replace with LLM-based or fine-tuned model.
    """

    POSITIVE_WORDS = {
        "good", "great", "excellent", "amazing", "awesome", "bullish",
        "up", "gain", "profit", "win", "success", "growth", "positive",
        "strong", "buy", "long", "moon", "rocket", "love", "best",
        "innovative", "breakthrough", "exciting", "confident", "optimistic",
    }

    NEGATIVE_WORDS = {
        "bad", "terrible", "awful", "bearish", "down", "loss", "fail",
        "crash", "dump", "sell", "short", "fear", "worry", "concern",
        "decline", "drop", "weak", "poor", "worst", "hate", "scam",
        "fraud", "manipulation", "disappointed", "pessimistic", "risk",
    }

    URGENT_WORDS = {
        "breaking", "urgent", "alert", "now", "immediately", "just",
        "happening", "live", "emergency", "critical", "warning",
    }

    DEFENSIVE_WORDS = {
        "but", "however", "despite", "although", "actually", "clarify",
        "explain", "misunderstood", "context", "false", "fake", "fud",
    }

    UNCERTAINTY_WORDS = {
        "maybe", "might", "could", "possibly", "uncertain", "unclear",
        "rumor", "speculation", "if", "whether", "depends",
    }

    async def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment using word matching."""
        words = set(text.lower().split())

        positive_count = len(words & self.POSITIVE_WORDS)
        negative_count = len(words & self.NEGATIVE_WORDS)

        # Calculate score
        total = positive_count + negative_count
        if total == 0:
            score = 0.0
            confidence = 0.3
        else:
            score = (positive_count - negative_count) / total
            confidence = min(0.9, 0.3 + (total * 0.1))

        # Detect tones
        tones = []
        if words & self.URGENT_WORDS:
            tones.append("urgent")
        if words & self.DEFENSIVE_WORDS:
            tones.append("defensive")
        if words & self.UNCERTAINTY_WORDS:
            tones.append("uncertain")
        if positive_count > negative_count:
            tones.append("positive")
        elif negative_count > positive_count:
            tones.append("negative")
        else:
            tones.append("neutral")

        return SentimentResult(
            score=score,
            confidence=confidence,
            tones=tones,
        )


class LLMSentimentAnalyzer(SentimentAnalyzer):
    """
    LLM-based sentiment analyzer for more nuanced analysis.

    Uses Claude or similar for deep sentiment and tone understanding.
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client

    async def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment using LLM."""
        prompt = f"""Analyze the sentiment and tone of this social media post about financial markets or companies.

Post: "{text}"

Provide:
1. Sentiment score from -1.0 (very negative) to 1.0 (very positive)
2. Confidence from 0.0 to 1.0
3. List of tone markers (e.g., urgent, defensive, sarcastic, uncertain, confident)

Respond in JSON format:
{{"score": float, "confidence": float, "tones": [string]}}"""

        response = await self.llm_client.generate(prompt)
        # Parse response (simplified - in production use proper JSON parsing)
        import json
        try:
            data = json.loads(response)
            return SentimentResult(
                score=float(data.get("score", 0)),
                confidence=float(data.get("confidence", 0.5)),
                tones=data.get("tones", []),
            )
        except (json.JSONDecodeError, KeyError):
            # Fallback to simple analyzer
            simple = SimpleSentimentAnalyzer()
            return await simple.analyze(text)


class EmbeddingGenerator:
    """Base class for generating text embeddings."""

    async def generate(self, text: str) -> list[float]:
        """Generate embedding vector for text."""
        raise NotImplementedError


class OpenAIEmbeddingGenerator(EmbeddingGenerator):
    """Generate embeddings using OpenAI API."""

    def __init__(self, api_key: str, model: str = "text-embedding-ada-002"):
        self.api_key = api_key
        self.model = model

    async def generate(self, text: str) -> list[float]:
        """Generate embedding using OpenAI."""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": text,
                    "model": self.model,
                },
            ) as response:
                data = await response.json()
                return data["data"][0]["embedding"]


class BotDetector:
    """Detect potential bot accounts."""

    BOT_INDICATORS = {
        # Username patterns
        "username_has_numbers": re.compile(r'\d{4,}'),
        "username_random_chars": re.compile(r'[a-z]{1,3}\d{3,}[a-z]{1,3}', re.I),

        # Bio patterns (simplified)
        "crypto_spam": re.compile(r'(airdrop|giveaway|dm for|free crypto)', re.I),
    }

    def is_likely_bot(self, account: Account) -> bool:
        """Check if account is likely a bot."""
        # Check username patterns
        if self.BOT_INDICATORS["username_has_numbers"].search(account.username):
            # Check follower ratio
            if account.follower_count < 100:
                return True

        # Very low engagement relative to account age
        # (Would need more account data for this check)

        return False

    def bot_probability(self, account: Account) -> float:
        """Calculate probability that account is a bot."""
        score = 0.0

        # Username checks
        if self.BOT_INDICATORS["username_has_numbers"].search(account.username):
            score += 0.2
        if self.BOT_INDICATORS["username_random_chars"].search(account.username):
            score += 0.3

        # Follower checks
        if account.follower_count < 10:
            score += 0.3
        elif account.follower_count < 50:
            score += 0.1

        return min(1.0, score)
