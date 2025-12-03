"""
LLM-powered reasoning for discourse analysis.

Uses Claude for deep analysis that goes beyond pattern matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import logging

from .client import LLMClient
from .prompts import PromptTemplates
from ..models.discourse import DiscourseSnapshot
from ..models.expectation import DiscourseExpectation
from ..models.delta import Delta, DeltaCluster
from ..models.event import EventClassification, EventType, EventSeverity

logger = logging.getLogger(__name__)


@dataclass
class AbsenceAnalysis:
    """Result of LLM absence detection analysis."""
    missing_topics: list[dict]
    missing_voices: list[dict]
    overall_assessment: str
    confidence: float
    possible_explanations: list[str]


@dataclass
class EventAnalysis:
    """Result of LLM event classification."""
    primary_event_type: str
    confidence: float
    alternative_types: list[dict]
    reasoning: str
    market_prediction: dict
    key_signals: list[str]


class DiscourseReasoner:
    """
    Uses LLM for deep reasoning about discourse patterns.

    Enhances rule-based detection with nuanced understanding.
    """

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.prompts = PromptTemplates()

    async def analyze_absence(
        self,
        snapshot: DiscourseSnapshot,
        expectation: DiscourseExpectation,
    ) -> AbsenceAnalysis:
        """
        Use LLM to analyze what's missing from discourse.

        This is the core innovation: understanding what SHOULD be
        discussed but isn't.
        """
        # Prepare inputs
        expected_topics = [t.topic_name for t in expectation.expected_topics[:10]]
        observed_topics = list(snapshot.topic_counts.keys())[:10]
        expected_voices = [v.username for v in expectation.expected_voices[:10]]
        observed_voices = [a.username for a in snapshot.active_accounts[:10]]

        prompt = self.prompts.absence_detection(
            entity=snapshot.entity,
            expected_topics=expected_topics,
            observed_topics=observed_topics,
            expected_voices=expected_voices,
            observed_voices=observed_voices,
        )

        try:
            result = await self.llm.generate_json(
                prompt=prompt,
                system=self.prompts.SYSTEM_CONTEXT,
            )

            return AbsenceAnalysis(
                missing_topics=result.get("missing_topics", []),
                missing_voices=result.get("missing_voices", []),
                overall_assessment=result.get("overall_assessment", ""),
                confidence=result.get("confidence", 0.5),
                possible_explanations=result.get("possible_explanations", []),
            )

        except Exception as e:
            logger.error(f"Absence analysis failed: {e}")
            return AbsenceAnalysis(
                missing_topics=[],
                missing_voices=[],
                overall_assessment="Analysis failed",
                confidence=0,
                possible_explanations=[],
            )

    async def classify_event(
        self,
        entity: str,
        deltas: list[Delta],
        context: Optional[str] = None,
    ) -> EventAnalysis:
        """
        Use LLM to classify detected deltas into event types.

        Provides more nuanced classification than rule-based matching.
        """
        delta_dicts = [
            {"type": d.delta_type.value, "description": d.description}
            for d in deltas
        ]

        prompt = self.prompts.event_classification(
            entity=entity,
            deltas=delta_dicts,
            context=context,
        )

        try:
            result = await self.llm.generate_json(
                prompt=prompt,
                system=self.prompts.SYSTEM_CONTEXT,
            )

            return EventAnalysis(
                primary_event_type=result.get("primary_event_type", "ANOMALY_DETECTED"),
                confidence=result.get("confidence", 0.5),
                alternative_types=result.get("alternative_types", []),
                reasoning=result.get("reasoning", ""),
                market_prediction=result.get("predicted_market_impact", {}),
                key_signals=result.get("key_signals", []),
            )

        except Exception as e:
            logger.error(f"Event classification failed: {e}")
            return EventAnalysis(
                primary_event_type="ANOMALY_DETECTED",
                confidence=0.3,
                alternative_types=[],
                reasoning="Classification failed",
                market_prediction={},
                key_signals=[],
            )

    async def analyze_sentiment_deeply(
        self,
        text: str,
        context: Optional[str] = None,
    ) -> dict:
        """
        Deep sentiment analysis using LLM.

        Goes beyond positive/negative to understand nuance.
        """
        prompt = self.prompts.sentiment_analysis(text, context)

        try:
            return await self.llm.generate_json(
                prompt=prompt,
                system=self.prompts.SYSTEM_CONTEXT,
            )
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {"sentiment_score": 0, "confidence": 0}

    async def analyze_tone_shift(
        self,
        entity: str,
        historical_tones: list[str],
        current_tones: list[str],
        sample_posts: list[str],
    ) -> dict:
        """Analyze detected tone shifts."""
        prompt = self.prompts.tone_shift_analysis(
            entity=entity,
            historical_tones=historical_tones,
            current_tones=current_tones,
            sample_posts=sample_posts,
        )

        try:
            return await self.llm.generate_json(
                prompt=prompt,
                system=self.prompts.SYSTEM_CONTEXT,
            )
        except Exception as e:
            logger.error(f"Tone shift analysis failed: {e}")
            return {"shift_detected": False}

    async def detect_coordination(
        self,
        entity: str,
        accounts: list[str],
        behavior_description: str,
        timing_info: str,
    ) -> dict:
        """Analyze whether behavior appears coordinated."""
        prompt = self.prompts.coordinated_behavior_detection(
            entity=entity,
            accounts=accounts,
            behavior_description=behavior_description,
            timing_info=timing_info,
        )

        try:
            return await self.llm.generate_json(
                prompt=prompt,
                system=self.prompts.SYSTEM_CONTEXT,
            )
        except Exception as e:
            logger.error(f"Coordination detection failed: {e}")
            return {"appears_coordinated": False}

    async def predict_market_impact(
        self,
        entity: str,
        event_type: str,
        event_severity: str,
        deltas: list[Delta],
    ) -> dict:
        """Predict market impact of detected event."""
        deltas_summary = "\n".join(f"- {d.description}" for d in deltas[:5])

        prompt = self.prompts.market_prediction(
            entity=entity,
            event_type=event_type,
            event_severity=event_severity,
            deltas_summary=deltas_summary,
        )

        try:
            return await self.llm.generate_json(
                prompt=prompt,
                system=self.prompts.SYSTEM_CONTEXT,
            )
        except Exception as e:
            logger.error(f"Market prediction failed: {e}")
            return {
                "predicted_direction": "neutral",
                "direction_confidence": 0.3,
            }

    def enhance_classification(
        self,
        rule_based: EventClassification,
        llm_analysis: EventAnalysis,
    ) -> EventClassification:
        """
        Combine rule-based and LLM classifications.

        Uses LLM to enhance but not override rule-based detection.
        """
        # If LLM is confident and disagrees, consider its input
        if llm_analysis.confidence > 0.7:
            # Map LLM type to enum
            try:
                llm_type = EventType[llm_analysis.primary_event_type]
            except KeyError:
                llm_type = EventType.ANOMALY_DETECTED

            # If rule-based is low confidence, prefer LLM
            if rule_based.primary_confidence < 0.5:
                rule_based.primary_type = llm_type
                rule_based.primary_confidence = llm_analysis.confidence
                rule_based.reasoning = llm_analysis.reasoning

            # Add LLM predictions if available
            if llm_analysis.market_prediction:
                pred = llm_analysis.market_prediction
                rule_based.predicted_direction = pred.get("direction")
                rule_based.direction_confidence = pred.get("direction_confidence", 0.5)
                rule_based.predicted_magnitude = pred.get("magnitude")
                rule_based.predicted_timing = pred.get("timing")

        return rule_based
