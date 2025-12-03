"""
Event store - persistence for detected events and deltas.

Provides storage and retrieval for all system data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Protocol
import logging
import json

from ..models.discourse import DiscourseSnapshot
from ..models.expectation import BaselinePattern
from ..models.delta import Delta, DeltaCluster
from ..models.event import DetectedEvent
from ..models.market import ValidationResult

logger = logging.getLogger(__name__)


class StorageBackend(Protocol):
    """Protocol for storage backends."""

    async def save(self, collection: str, key: str, data: dict) -> None:
        """Save data to storage."""
        ...

    async def load(self, collection: str, key: str) -> Optional[dict]:
        """Load data from storage."""
        ...

    async def query(
        self,
        collection: str,
        filters: dict,
        limit: int = 100,
    ) -> list[dict]:
        """Query data from storage."""
        ...

    async def delete(self, collection: str, key: str) -> None:
        """Delete data from storage."""
        ...


class InMemoryBackend:
    """
    In-memory storage backend for development/testing.

    For production, use TimescaleDB, Redis, or similar.
    """

    def __init__(self):
        self.data: dict[str, dict[str, dict]] = {}

    async def save(self, collection: str, key: str, data: dict) -> None:
        if collection not in self.data:
            self.data[collection] = {}
        self.data[collection][key] = data

    async def load(self, collection: str, key: str) -> Optional[dict]:
        if collection not in self.data:
            return None
        return self.data[collection].get(key)

    async def query(
        self,
        collection: str,
        filters: dict,
        limit: int = 100,
    ) -> list[dict]:
        if collection not in self.data:
            return []

        results = []
        for key, item in self.data[collection].items():
            # Simple filter matching
            matches = True
            for field, value in filters.items():
                if item.get(field) != value:
                    matches = False
                    break
            if matches:
                results.append(item)
                if len(results) >= limit:
                    break

        return results

    async def delete(self, collection: str, key: str) -> None:
        if collection in self.data and key in self.data[collection]:
            del self.data[collection][key]


class EventStore:
    """
    Unified storage for all system data.

    Handles:
    - Discourse snapshots
    - Baseline patterns
    - Detected deltas
    - Events
    - Validation results
    """

    def __init__(self, backend: Optional[StorageBackend] = None):
        self.backend = backend or InMemoryBackend()

    # Snapshot operations
    async def save_snapshot(self, snapshot: DiscourseSnapshot) -> None:
        """Save a discourse snapshot."""
        await self.backend.save(
            collection="snapshots",
            key=snapshot.snapshot_id,
            data={
                "snapshot_id": snapshot.snapshot_id,
                "entity": snapshot.entity,
                "window_start": snapshot.window_start.isoformat(),
                "window_end": snapshot.window_end.isoformat(),
                "total_posts": snapshot.total_posts,
                "unique_authors": snapshot.unique_authors,
                "total_engagement": snapshot.total_engagement,
                "topic_counts": snapshot.topic_counts,
                "topic_sentiments": snapshot.topic_sentiments,
                "avg_sentiment": snapshot.avg_sentiment,
                "dominant_tones": snapshot.dominant_tones,
            }
        )

    async def get_snapshots(
        self,
        entity: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get snapshots for an entity in a time range."""
        return await self.backend.query(
            collection="snapshots",
            filters={"entity": entity},
            limit=limit,
        )

    # Baseline operations
    async def save_baseline(self, baseline: BaselinePattern) -> None:
        """Save a baseline pattern."""
        await self.backend.save(
            collection="baselines",
            key=f"{baseline.entity}_{baseline.time_window.value}",
            data={
                "entity": baseline.entity,
                "time_window": baseline.time_window.value,
                "avg_posts_per_window": baseline.avg_posts_per_window,
                "post_stddev": baseline.post_stddev,
                "hourly_volume_pattern": baseline.hourly_volume_pattern,
                "daily_volume_pattern": baseline.daily_volume_pattern,
                "avg_sentiment": baseline.avg_sentiment,
                "sentiment_stddev": baseline.sentiment_stddev,
                "sample_size": baseline.sample_size,
                "last_updated": baseline.last_updated.isoformat() if baseline.last_updated else None,
            }
        )

    async def get_baseline(self, entity: str, time_window: str) -> Optional[dict]:
        """Get baseline for an entity."""
        return await self.backend.load(
            collection="baselines",
            key=f"{entity}_{time_window}",
        )

    # Delta operations
    async def save_delta(self, delta: Delta) -> None:
        """Save a detected delta."""
        await self.backend.save(
            collection="deltas",
            key=delta.delta_id,
            data=delta.to_dict(),
        )

    async def get_deltas(
        self,
        entity: Optional[str] = None,
        delta_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get deltas with optional filters."""
        filters = {}
        if entity:
            filters["entity"] = entity
        if delta_type:
            filters["delta_type"] = delta_type

        return await self.backend.query(
            collection="deltas",
            filters=filters,
            limit=limit,
        )

    # Event operations
    async def save_event(self, event: DetectedEvent) -> None:
        """Save a detected event."""
        await self.backend.save(
            collection="events",
            key=event.event_id,
            data=event.to_dict(),
        )

    async def get_event(self, event_id: str) -> Optional[dict]:
        """Get a specific event."""
        return await self.backend.load(
            collection="events",
            key=event_id,
        )

    async def get_events(
        self,
        entity: Optional[str] = None,
        event_type: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> list[dict]:
        """Get events with optional filters."""
        filters = {}
        if entity:
            filters["entity"] = entity
        if event_type:
            filters["event_type"] = event_type

        return await self.backend.query(
            collection="events",
            filters=filters,
            limit=limit,
        )

    async def update_event(self, event_id: str, updates: dict) -> None:
        """Update an event with new data."""
        existing = await self.backend.load("events", event_id)
        if existing:
            existing.update(updates)
            existing["updated_at"] = datetime.utcnow().isoformat()
            await self.backend.save("events", event_id, existing)

    # Validation operations
    async def save_validation(self, validation: ValidationResult) -> None:
        """Save a validation result."""
        await self.backend.save(
            collection="validations",
            key=validation.validation_id,
            data={
                "validation_id": validation.validation_id,
                "event_id": validation.event_id,
                "entity": validation.entity,
                "tickers": validation.tickers,
                "validated_at": validation.validated_at.isoformat(),
                "validated": validation.validated,
                "validation_strength": validation.validation_strength,
                "avg_overall_score": validation.avg_overall_score,
            }
        )

    async def get_validations(
        self,
        entity: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get validation results."""
        filters = {}
        if entity:
            filters["entity"] = entity

        return await self.backend.query(
            collection="validations",
            filters=filters,
            limit=limit,
        )

    # Analytics
    async def get_entity_stats(self, entity: str) -> dict:
        """Get aggregate statistics for an entity."""
        deltas = await self.get_deltas(entity=entity)
        events = await self.get_events(entity=entity)
        validations = await self.get_validations(entity=entity)

        validated_correct = sum(1 for v in validations if v.get("validated"))

        return {
            "entity": entity,
            "total_deltas": len(deltas),
            "total_events": len(events),
            "total_validations": len(validations),
            "validation_accuracy": (
                validated_correct / len(validations)
                if validations else 0
            ),
        }

    async def cleanup_old_data(self, days_to_keep: int = 30) -> dict:
        """Remove data older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)

        # Would implement actual cleanup in production
        return {
            "cutoff": cutoff.isoformat(),
            "status": "cleanup not implemented for in-memory backend",
        }
