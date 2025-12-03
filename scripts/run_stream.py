#!/usr/bin/env python3
"""
Main runner script for the Discourse Delta Detection System.

Starts the real-time stream processor and event detection pipeline.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from src.config.settings import get_settings
from src.ingestion.x_client import XClient
from src.ingestion.stream_processor import StreamProcessor
from src.ingestion.preprocessor import Preprocessor
from src.expectation.baseline_builder import BaselineBuilder
from src.expectation.context_triggers import TriggerManager
from src.expectation.generator import ExpectationGenerator
from src.detection.delta_detector import DeltaDetector
from src.detection.classifier import EventClassifier
from src.validation.market_tracker import MarketTracker, MarketDataConfig
from src.validation.correlator import DeltaMarketCorrelator
from src.storage.event_store import EventStore
from src.llm.client import ClaudeClient
from src.llm.reasoning import DiscourseReasoner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class DiscourseEngine:
    """
    Main engine orchestrating all components.

    Connects ingestion -> expectation -> detection -> validation.
    """

    def __init__(self):
        self.settings = get_settings()

        # Initialize components
        self._init_ingestion()
        self._init_expectation()
        self._init_detection()
        self._init_validation()
        self._init_storage()

        # State
        self.running = False

    def _init_ingestion(self):
        """Initialize data ingestion components."""
        self.x_client = XClient(self.settings.x_api)
        self.preprocessor = Preprocessor()
        self.stream_processor = StreamProcessor(
            x_client=self.x_client,
            preprocessor=self.preprocessor,
            settings=self.settings,
        )

    def _init_expectation(self):
        """Initialize expectation modeling components."""
        self.baseline_builder = BaselineBuilder(
            lookback_days=self.settings.detection.baseline_lookback_days,
        )
        self.trigger_manager = TriggerManager()
        self.expectation_generator = ExpectationGenerator(
            baseline_builder=self.baseline_builder,
            trigger_manager=self.trigger_manager,
        )

    def _init_detection(self):
        """Initialize delta detection components."""
        self.delta_detector = DeltaDetector(
            expectation_generator=self.expectation_generator,
        )
        self.event_classifier = EventClassifier()

    def _init_validation(self):
        """Initialize market validation components."""
        market_config = MarketDataConfig(
            provider=self.settings.market_data.provider,
            api_key=self.settings.market_data.api_key,
        )
        self.market_tracker = MarketTracker(market_config)
        self.correlator = DeltaMarketCorrelator(self.market_tracker)

    def _init_storage(self):
        """Initialize storage."""
        self.event_store = EventStore()

    async def on_snapshot(self, snapshot):
        """Handle new discourse snapshot."""
        logger.info(f"Processing snapshot for {snapshot.entity}: {snapshot.total_posts} posts")

        # Generate expectation
        expectation = self.expectation_generator.generate_expectation(
            entity=snapshot.entity,
            window_start=snapshot.window_start,
            window_end=snapshot.window_end,
        )

        # Detect deltas
        deltas = self.delta_detector.detect(snapshot, expectation)

        if deltas:
            logger.info(f"Detected {len(deltas)} deltas for {snapshot.entity}")

            # Save deltas
            for delta in deltas:
                await self.event_store.save_delta(delta)

            # Create event if significant
            high_confidence = [d for d in deltas if d.confidence > 0.6]
            if high_confidence:
                event = self.event_classifier.create_event(
                    entity=snapshot.entity,
                    deltas=high_confidence,
                )

                logger.info(f"Created event: {event.title}")

                await self.event_store.save_event(event)
                await self.correlator.track_event(event)

        # Save snapshot
        await self.event_store.save_snapshot(snapshot)

    async def start(self):
        """Start the engine."""
        logger.info("Starting Discourse Delta Detection Engine")
        self.running = True

        # Set up callbacks
        self.stream_processor.on_snapshot = self.on_snapshot

        # Start components
        try:
            await asyncio.gather(
                self.stream_processor.start(),
                self._validation_loop(),
            )
        except asyncio.CancelledError:
            logger.info("Engine shutdown requested")
        finally:
            await self.stop()

    async def _validation_loop(self):
        """Periodically validate pending predictions."""
        while self.running:
            await asyncio.sleep(60 * 5)  # Every 5 minutes

            validations = await self.correlator.validate_pending()
            for validation in validations:
                await self.event_store.save_validation(validation)
                logger.info(
                    f"Validated event {validation.event_id}: "
                    f"{validation.validation_strength}"
                )

    async def stop(self):
        """Stop the engine."""
        logger.info("Stopping engine")
        self.running = False
        await self.stream_processor.stop()
        await self.x_client.close()
        await self.market_tracker.close()


async def main():
    """Main entry point."""
    engine = DiscourseEngine()

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(engine.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    await engine.start()


if __name__ == "__main__":
    asyncio.run(main())
