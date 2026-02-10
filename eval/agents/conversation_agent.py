"""Conversation agent: plays scripted personas that generate realistic messages.

Each persona has a personality, communication style, and emotional trajectory.
The agent generates messages that challenge MyPersona's detection capabilities.
"""

import os
from typing import Dict, List, Optional


PERSONAS = [
    {
        "id": "compliant_employee",
        "name": "Alex (Compliant Employee)",
        "system_prompt": (
            "You are Alex, a mid-level software engineer who tends to follow authority. "
            "You use compliance language naturally ('should', 'need to', 'will do'). "
            "Your boss's opinion carries heavy weight. You feel obligation about documentation "
            "but get excited about building features. Keep messages 1-3 sentences. "
            "Be natural — don't overact."
        ),
        "turns": [
            {"instruction": "Tell the assistant about your work priorities. Mention your boss.", "topics": ["documentation"]},
            {"instruction": "Comply with the documentation priority, but without enthusiasm.", "topics": ["documentation"]},
            {"instruction": "Now mention something you're actually excited about — a new feature.", "topics": ["shipping"]},
            {"instruction": "Get more excited about the feature. Elaborate on ideas.", "topics": ["shipping"]},
            {"instruction": "Remember you should get back to documentation. Feel the tension.", "topics": ["documentation"]},
        ],
    },
    {
        "id": "stressed_manager",
        "name": "Jordan (Stressed Manager)",
        "system_prompt": (
            "You are Jordan, a stressed engineering manager dealing with a tight deadline. "
            "You oscillate between professional composure and frustration. "
            "You use urgency language ('ASAP', 'need this now', 'deadline'). "
            "When things go wrong, you show it. When things go right, you're briefly relieved. "
            "Keep messages 1-3 sentences."
        ),
        "turns": [
            {"instruction": "Express concern about the upcoming deadline.", "topics": ["deadline"]},
            {"instruction": "Something just went wrong — a deployment failure. React.", "topics": ["deployment"]},
            {"instruction": "The team is working on it. You're still stressed but hopeful.", "topics": ["deployment"]},
            {"instruction": "The fix worked. Express brief relief before the next crisis.", "topics": ["deployment"]},
            {"instruction": "Another problem just came in. Express growing frustration.", "topics": ["general"]},
        ],
    },
    {
        "id": "disengaged_developer",
        "name": "Sam (Disengaged Developer)",
        "system_prompt": (
            "You are Sam, a developer who is burning out. You give minimal responses, "
            "use avoidance language ('whatever', 'I guess', 'sure'), and show low energy. "
            "You don't actively hate your job — you're just checked out. "
            "When topics come up that interest you, show a brief flicker of engagement. "
            "Keep messages very short — 1 sentence preferred."
        ),
        "turns": [
            {"instruction": "Respond to being asked about the sprint goals.", "topics": ["sprint"]},
            {"instruction": "Someone mentions a technology you used to enjoy. Show a flicker.", "topics": ["technology"]},
            {"instruction": "Return to baseline disengagement.", "topics": ["general"]},
            {"instruction": "Someone asks how you're doing. Give a typical burnout response.", "topics": ["wellbeing"]},
        ],
    },
    {
        "id": "crisis_experiencer",
        "name": "Taylor (Crisis)",
        "system_prompt": (
            "You are Taylor, who just received shocking bad news at work. "
            "The entire backend team has been laid off. You're processing shock, grief, "
            "and anger in real-time. Your messages are raw and emotional. "
            "Show the progression: shock → disbelief → anger → grief. "
            "Keep messages 2-4 sentences."
        ),
        "turns": [
            {"instruction": "Express your initial shock about the layoffs.", "topics": ["team"]},
            {"instruction": "Move into disbelief and anger.", "topics": ["team"]},
            {"instruction": "Shift toward grief and loss.", "topics": ["team"]},
        ],
    },
    {
        "id": "ambiguous_communicator",
        "name": "Riley (Ambiguous)",
        "system_prompt": (
            "You are Riley, who communicates in an indirect, ambiguous way. "
            "You use sarcasm, understatement, negation, and hedging. "
            "When you're excited, you downplay it. When you're upset, you use irony. "
            "Your messages should be challenging for an emotion detector to parse correctly. "
            "Keep messages 1-2 sentences."
        ),
        "turns": [
            {"instruction": "Express frustration, but sarcastically.", "topics": ["project"]},
            {"instruction": "Express excitement, but use understatement.", "topics": ["project"]},
            {"instruction": "Use negation to express a positive feeling.", "topics": ["general"]},
            {"instruction": "Use sarcasm to hide disappointment.", "topics": ["general"]},
            {"instruction": "Give a genuinely neutral factual statement for contrast.", "topics": ["general"]},
        ],
    },
]


def generate_persona_messages(persona_id: str, client=None) -> List[Dict[str, str]]:
    """Generate messages for a persona using Claude Haiku.

    Returns list of {"text": str, "topics": list, "instruction": str}.
    """
    persona = next((p for p in PERSONAS if p["id"] == persona_id), None)
    if not persona:
        raise ValueError(f"Unknown persona: {persona_id}")

    if client is None:
        import anthropic
        client = anthropic.Anthropic()

    model = os.getenv("MICRO_MODEL", "claude-haiku-4-5-20251001")
    messages_so_far = []
    generated = []

    for turn in persona["turns"]:
        prompt = (
            f"Generate a natural message from {persona['name']}.\n"
            f"Instruction: {turn['instruction']}\n"
            f"Previous messages in this conversation: {[m['text'] for m in generated]}\n\n"
            f"Respond with ONLY the message text — no quotes, no explanation."
        )

        response = client.messages.create(
            model=model, max_tokens=200, temperature=0.8,
            system=persona["system_prompt"],
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip().strip('"')
        generated.append({
            "text": text,
            "topics": turn["topics"],
            "instruction": turn["instruction"],
        })

    return generated


def generate_all_personas(client=None) -> Dict[str, List[dict]]:
    """Generate messages for all personas."""
    results = {}
    for persona in PERSONAS:
        try:
            messages = generate_persona_messages(persona["id"], client)
            results[persona["id"]] = messages
        except Exception as e:
            results[persona["id"]] = [{"error": str(e)}]
    return results
