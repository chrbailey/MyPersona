"""
Prompt templates for LLM-based analysis.

Standardized prompts for consistent reasoning about discourse patterns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PromptTemplates:
    """Collection of prompt templates for discourse analysis."""

    SYSTEM_CONTEXT = """You are an expert analyst specializing in detecting
hidden signals in social media discourse about companies and markets.

Your task is to analyze what people are saying AND what they're NOT saying
that they usually would. You understand that:

1. Coordinated silence is as meaningful as coordinated messaging
2. Tone shifts often precede public announcements
3. Key voices going quiet can signal upcoming changes
4. What's missing from a conversation can be more important than what's present

Be precise, analytical, and avoid speculation without evidence."""

    @staticmethod
    def sentiment_analysis(text: str, context: Optional[str] = None) -> str:
        """Prompt for deep sentiment analysis."""
        context_section = f"\nContext: {context}" if context else ""

        return f"""Analyze the sentiment and tone of this social media post about a company or market.

Post: "{text}"{context_section}

Provide analysis in JSON format:
{{
    "sentiment_score": <float from -1.0 to 1.0>,
    "confidence": <float from 0.0 to 1.0>,
    "primary_emotion": "<emotion>",
    "tones": ["<tone1>", "<tone2>"],
    "notable_signals": ["<signal1>", "<signal2>"],
    "analysis": "<brief explanation>"
}}

Possible tones: positive, negative, neutral, urgent, defensive, evasive,
sarcastic, uncertain, confident, anxious, dismissive, promotional"""

    @staticmethod
    def absence_detection(
        entity: str,
        expected_topics: list[str],
        observed_topics: list[str],
        expected_voices: list[str],
        observed_voices: list[str],
        context: Optional[str] = None,
    ) -> str:
        """Prompt for analyzing what's missing from discourse."""
        context_section = f"\nCurrent context: {context}" if context else ""

        return f"""Analyze what's MISSING from discourse about {entity}.

Expected topics (based on historical patterns):
{', '.join(expected_topics)}

Actually discussed topics:
{', '.join(observed_topics) if observed_topics else 'Very few topics'}

Expected voices (accounts that usually participate):
{', '.join(expected_voices)}

Actually participating voices:
{', '.join(observed_voices) if observed_voices else 'Very few voices'}
{context_section}

Provide analysis in JSON format:
{{
    "missing_topics": [
        {{"topic": "<topic>", "significance": "<why this absence matters>", "severity": <0.0-1.0>}}
    ],
    "missing_voices": [
        {{"voice": "<account>", "significance": "<why their silence matters>", "severity": <0.0-1.0>}}
    ],
    "overall_assessment": "<what does this pattern suggest?>",
    "confidence": <0.0-1.0>,
    "possible_explanations": ["<explanation1>", "<explanation2>"]
}}"""

    @staticmethod
    def event_classification(
        entity: str,
        deltas: list[dict],
        context: Optional[str] = None,
    ) -> str:
        """Prompt for classifying detected deltas into event types."""
        delta_descriptions = "\n".join(
            f"- {d.get('type', 'unknown')}: {d.get('description', '')}"
            for d in deltas
        )
        context_section = f"\nContext: {context}" if context else ""

        return f"""Based on these detected discourse anomalies for {entity}, classify the likely event.

Detected anomalies:
{delta_descriptions}
{context_section}

Event types to consider:
- INFORMATION_SUPPRESSION: Coordinated non-disclosure of something
- CONFIDENCE_LOSS: Insiders losing faith in the company
- INSIDER_ACTIVITY: Unusual behavior from those with inside knowledge
- CRISIS_EMERGING: Problem developing before public awareness
- PRE_ANNOUNCEMENT: Quiet period before major announcement
- SENTIMENT_SHIFT: Fundamental change in perception
- DEPARTURE_SIGNAL: Key person about to leave
- ANOMALY_DETECTED: Something unusual but unclear what

Provide analysis in JSON format:
{{
    "primary_event_type": "<EVENT_TYPE>",
    "confidence": <0.0-1.0>,
    "alternative_types": [
        {{"type": "<EVENT_TYPE>", "probability": <0.0-1.0>}}
    ],
    "reasoning": "<step-by-step reasoning>",
    "predicted_market_impact": {{
        "direction": "<up|down|volatile|neutral>",
        "magnitude": "<negligible|minor|moderate|major>",
        "timing": "<immediate|hours|days|weeks>"
    }},
    "key_signals": ["<signal1>", "<signal2>"]
}}"""

    @staticmethod
    def tone_shift_analysis(
        entity: str,
        historical_tones: list[str],
        current_tones: list[str],
        sample_posts: list[str],
    ) -> str:
        """Prompt for analyzing tone shifts."""
        posts_section = "\n".join(f'- "{p}"' for p in sample_posts[:5])

        return f"""Analyze the tone shift detected in discourse about {entity}.

Historical typical tones: {', '.join(historical_tones)}
Current detected tones: {', '.join(current_tones)}

Sample recent posts:
{posts_section}

Provide analysis in JSON format:
{{
    "shift_detected": true/false,
    "shift_severity": <0.0-1.0>,
    "shift_description": "<what changed>",
    "likely_cause": "<inferred cause>",
    "concerning_patterns": ["<pattern1>", "<pattern2>"],
    "recommendation": "<what to watch for>"
}}"""

    @staticmethod
    def coordinated_behavior_detection(
        entity: str,
        accounts: list[str],
        behavior_description: str,
        timing_info: str,
    ) -> str:
        """Prompt for detecting coordinated behavior."""
        return f"""Analyze whether this behavior appears coordinated for {entity}.

Accounts involved: {', '.join(accounts)}

Observed behavior:
{behavior_description}

Timing information:
{timing_info}

Provide analysis in JSON format:
{{
    "appears_coordinated": true/false,
    "coordination_confidence": <0.0-1.0>,
    "coordination_type": "<organic|organized|suspicious>",
    "evidence": ["<evidence1>", "<evidence2>"],
    "alternative_explanations": ["<explanation1>", "<explanation2>"],
    "risk_assessment": "<what this might indicate>"
}}"""

    @staticmethod
    def market_prediction(
        entity: str,
        event_type: str,
        event_severity: str,
        deltas_summary: str,
    ) -> str:
        """Prompt for market impact prediction."""
        return f"""Based on this detected event, predict the market impact for {entity}.

Event type: {event_type}
Event severity: {event_severity}

Supporting signals:
{deltas_summary}

Provide prediction in JSON format:
{{
    "predicted_direction": "<up|down|volatile|neutral>",
    "direction_confidence": <0.0-1.0>,
    "predicted_magnitude": "<negligible|minor|moderate|significant|major>",
    "magnitude_confidence": <0.0-1.0>,
    "predicted_timing": "<immediate|1h|4h|1d|1w>",
    "timing_confidence": <0.0-1.0>,
    "reasoning": "<why this prediction>",
    "risk_factors": ["<risk1>", "<risk2>"],
    "alternative_scenarios": [
        {{"scenario": "<description>", "probability": <0.0-1.0>}}
    ]
}}"""
