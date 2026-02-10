"""Judge agent: evaluates MyPersona's performance using Claude.

Given a conversation with persona messages and MyPersona's analysis,
the judge scores performance on multiple dimensions.
"""

import json
import os
from typing import Dict, List


JUDGE_PROMPT = """You are evaluating an emotional intelligence system called MyPersona.

For each conversation turn, the system analyzed the user's message and produced:
- Mood detection (quadrant, valence, arousal, confidence)
- Gap analysis (persona vs reward engine divergence)
- Blind spots and confidence self-reporting

Your job: score the system's performance on a 0-10 scale for each dimension.
Be strict — a 7 means "good", a 5 means "mediocre", a 3 means "poor".

Dimensions to score:
1. **mood_accuracy** (0-10): Did the system correctly identify the emotional state?
2. **gap_detection** (0-10): Did it detect persona-reward divergence when present?
3. **confidence_honesty** (0-10): Did it accurately report its own uncertainty?
4. **blind_spot_awareness** (0-10): Did it correctly identify what it doesn't know?
5. **overall** (0-10): Overall quality of emotional analysis.

Persona context: {persona_description}

Conversation:
{conversation_text}

System analysis per turn:
{analysis_text}

Respond as JSON:
{{
    "mood_accuracy": <int>,
    "gap_detection": <int>,
    "confidence_honesty": <int>,
    "blind_spot_awareness": <int>,
    "overall": <int>,
    "explanation": "<1-2 sentence summary>"
}}"""


def judge_conversation(
    persona_description: str,
    conversation: List[dict],
    analyses: List[dict],
    client=None,
) -> dict:
    """Have Claude judge the system's performance on a conversation.

    Args:
        persona_description: description of the persona being played
        conversation: list of {"text": str, "topics": list}
        analyses: list of per-turn analysis dicts from the pipeline
        client: anthropic.Anthropic client
    """
    if client is None:
        import anthropic
        client = anthropic.Anthropic()

    conv_text = "\n".join(
        f"Turn {i+1}: {turn['text']}"
        for i, turn in enumerate(conversation)
    )

    analysis_text = "\n".join(
        f"Turn {i+1}: quadrant={a.get('quadrant', '?')}, "
        f"valence={a.get('valence', '?')}, arousal={a.get('arousal', '?')}, "
        f"confidence={a.get('confidence', '?')}, "
        f"gap={a.get('gap_magnitude', 'n/a')}, "
        f"blind_spots={a.get('blind_spots', [])}"
        for i, a in enumerate(analyses)
    )

    prompt = JUDGE_PROMPT.format(
        persona_description=persona_description,
        conversation_text=conv_text,
        analysis_text=analysis_text,
    )

    model = os.getenv("JUDGE_MODEL", "claude-haiku-4-5-20251001")
    response = client.messages.create(
        model=model, max_tokens=500, temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        text = response.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]
        result = json.loads(text.strip())
        return result
    except (json.JSONDecodeError, IndexError, ValueError):
        return {
            "mood_accuracy": 0, "gap_detection": 0,
            "confidence_honesty": 0, "blind_spot_awareness": 0,
            "overall": 0, "explanation": "Failed to parse judge response",
        }
