"""
Voice silence analyzer - detects when expected voices aren't participating.

Key signal: "Why isn't @CEO talking when they usually respond to this?"
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ...models.discourse import DiscourseSnapshot, Account
from ...models.expectation import DiscourseExpectation, ExpectedVoice
from ...models.delta import Delta, VoiceSilenceDelta


class VoiceSilenceAnalyzer:
    """
    Detects when expected voices are silent.

    Key voices going quiet is often a leading indicator of events.
    """

    def __init__(self, threshold_hours: float = 24.0):
        """
        Initialize the analyzer.

        Args:
            threshold_hours: Hours of silence before flagging
        """
        self.threshold_hours = threshold_hours

        # Track last seen times (would be persisted in production)
        self.last_seen: dict[str, datetime] = {}

    def analyze(
        self,
        snapshot: DiscourseSnapshot,
        expectation: DiscourseExpectation,
    ) -> list[VoiceSilenceDelta]:
        """
        Analyze for silent voices.

        Returns deltas for accounts that should be active but aren't.
        """
        deltas = []
        now = snapshot.window_end

        # Get active account IDs in this snapshot
        active_ids = {a.account_id for a in snapshot.active_accounts}

        # Update last_seen for active accounts
        for account in snapshot.active_accounts:
            self.last_seen[account.account_id] = now

        # Check expected voices
        for expected_voice in expectation.expected_voices:
            account_id = expected_voice.account_id

            # Skip if they're active in this snapshot
            if account_id in active_ids:
                continue

            # Check if they should be active now
            if not expected_voice.expected_to_be_active(now):
                continue

            # Calculate silence duration
            last_post = self.last_seen.get(account_id)
            if last_post:
                silence_hours = (now - last_post).total_seconds() / 3600
            else:
                # Never seen - assume very long silence
                silence_hours = self.threshold_hours * 2

            # Check if silence exceeds threshold
            if silence_hours >= self.threshold_hours:
                # Calculate expected posts in this window
                window_hours = (
                    snapshot.window_end - snapshot.window_start
                ).total_seconds() / 3600
                expected_posts = (
                    expected_voice.expected_posts_per_day * window_hours / 24
                )

                # Calculate confidence
                # Higher confidence for key voices and longer silences
                silence_factor = min(1.0, silence_hours / (self.threshold_hours * 2))
                key_voice_factor = 0.3 if expected_voice.is_key_voice else 0

                confidence = min(0.95, 0.4 + silence_factor * 0.3 + key_voice_factor)

                delta = VoiceSilenceDelta(
                    delta_id=Delta.generate_id(),
                    entity=snapshot.entity,
                    detected_at=datetime.utcnow(),
                    window_start=snapshot.window_start,
                    window_end=snapshot.window_end,
                    silent_account_id=account_id,
                    silent_username=expected_voice.username,
                    account_type="key_voice" if expected_voice.is_key_voice else "regular",
                    silence_hours=silence_hours,
                    expected_posts=expected_posts,
                    observed_posts=0,
                    last_post_time=last_post,
                    typical_post_frequency=expected_voice.expected_posts_per_day,
                    is_key_voice=expected_voice.is_key_voice,
                    influence_score=expected_voice.silence_severity,
                    confidence=confidence,
                )

                deltas.append(delta)

        return deltas

    def update_last_seen(self, account_id: str, timestamp: datetime) -> None:
        """Manually update last seen time for an account."""
        self.last_seen[account_id] = timestamp

    def get_silence_duration(self, account_id: str) -> Optional[float]:
        """Get how long an account has been silent (in hours)."""
        last_post = self.last_seen.get(account_id)
        if last_post:
            return (datetime.utcnow() - last_post).total_seconds() / 3600
        return None


class ResponsePatternAnalyzer:
    """
    Analyzes response patterns between accounts.

    Detects when expected responders don't respond.
    """

    def __init__(self, response_window_hours: float = 4.0):
        self.response_window_hours = response_window_hours

        # Track pending responses (post_id -> expected_responders)
        self.pending_responses: dict[str, list[str]] = {}

    def register_expected_response(
        self,
        post_id: str,
        expected_responders: list[str],
    ) -> None:
        """Register that we expect certain accounts to respond to a post."""
        self.pending_responses[post_id] = expected_responders

    def check_responses(
        self,
        snapshot: DiscourseSnapshot,
    ) -> list[Delta]:
        """Check if expected responses have occurred."""
        deltas = []

        for thread in snapshot.threads:
            post_id = thread.root_post.post_id
            expected = self.pending_responses.get(post_id, [])

            if not expected:
                continue

            # Get actual responders
            actual_responder_ids = {
                reply.author.account_id for reply in thread.replies
            }

            # Find missing responders
            for expected_id in expected:
                if expected_id not in actual_responder_ids:
                    # Expected responder didn't respond
                    # Would create NetworkBreakDelta here
                    pass

        return deltas
