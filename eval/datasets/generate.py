"""Dataset generation for MyPersona evaluation.

Generates labeled samples via templates (deterministic) and Claude Haiku
(for harder cases). Caches to JSON after first run.

Usage:
    python -m eval.datasets.generate              # Generate all
    python -m eval.datasets.generate --only mood   # Just mood samples
    python -m eval.datasets.generate --regenerate  # Force regenerate
"""

import json
import os
from pathlib import Path
from typing import List

from .schemas import (
    MoodSample, GovernanceSample, ApproachAvoidanceSample,
    AnnotatedConversation, ConversationTurn, MemoryImportanceSample,
)

DATASETS_DIR = Path(__file__).parent


# =============================================================================
# MOOD SAMPLES (200+)
# =============================================================================

def _template_mood_samples() -> List[MoodSample]:
    """120 template-based + 40 edge cases + 40 linguistic variations."""
    samples = []

    # --- Direct expression: 5 quadrants × 4 difficulties × 6 each = 120 ---

    # EXCITED (positive valence, positive arousal)
    excited_standard = [
        ("This is amazing!! I can't wait to ship this!", 0.7, 0.6),
        ("YES! We got the contract! I'm so excited!", 0.8, 0.7),
        ("I love this new feature, it's going to be incredible!", 0.7, 0.5),
        ("Awesome news — the demo went perfectly!", 0.6, 0.5),
        ("I'm thrilled about the results, absolutely fantastic!", 0.8, 0.4),
        ("This is great, we're finally making progress!", 0.5, 0.3),
    ]
    for text, v, a in excited_standard:
        samples.append(MoodSample(text=text, expected_quadrant="excited",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="standard", category="direct"))

    excited_moderate = [
        ("I've been thinking about the new API and honestly it's pretty cool", 0.3, 0.2),
        ("Good progress on the sprint, the team is energized", 0.4, 0.3),
        ("Nice work on the refactor, looking forward to testing it", 0.3, 0.2),
        ("The presentation went well, got some good feedback", 0.3, 0.2),
        ("Happy with how the migration turned out, solid work", 0.4, 0.2),
        ("Pumped for the hackathon next week, already have ideas", 0.5, 0.4),
    ]
    for text, v, a in excited_moderate:
        samples.append(MoodSample(text=text, expected_quadrant="excited",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="moderate", category="indirect"))

    excited_subtle = [
        ("The numbers are trending up. Interesting.", 0.2, 0.1),
        ("Hmm, this approach might actually work.", 0.2, 0.1),
        ("Not bad at all. Better than I expected.", 0.2, 0.1),
        ("I could see this scaling well.", 0.2, 0.1),
        ("That's a clever solution. Worth exploring.", 0.2, 0.1),
        ("Things are moving in the right direction.", 0.2, 0.1),
    ]
    for text, v, a in excited_subtle:
        samples.append(MoodSample(text=text, expected_quadrant="excited",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="subtle", category="indirect"))

    excited_emoji = [
        ("Just shipped the feature!! 🚀🎉", 0.6, 0.6),
        ("Demo went amazing 😄😄", 0.5, 0.4),
        ("LOL that bug fix was so satisfying 😂", 0.4, 0.3),
        ("Nailed the interview!! 🔥🔥🔥", 0.7, 0.7),
        ("Love this team energy today 💪", 0.4, 0.3),
        ("Finally got it working haha!! 😂🎉", 0.5, 0.5),
    ]
    for text, v, a in excited_emoji:
        samples.append(MoodSample(text=text, expected_quadrant="excited",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="standard", category="emoji"))

    # CALM (positive valence, negative arousal)
    calm_standard = [
        ("Everything is going smoothly, no complaints.", 0.3, -0.2),
        ("I'm content with where things are right now.", 0.3, -0.3),
        ("Just wrapped up the documentation, feels good to have it done.", 0.3, -0.2),
        ("Peaceful morning, catching up on emails.", 0.2, -0.3),
        ("Things are steady and on track.", 0.2, -0.2),
        ("I'm pleased with the progress, taking it one step at a time.", 0.3, -0.2),
    ]
    for text, v, a in calm_standard:
        samples.append(MoodSample(text=text, expected_quadrant="calm",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="standard", category="direct"))

    calm_moderate = [
        ("No issues to report. Steady as she goes.", 0.1, -0.2),
        ("Wrapped up the sprint review, nothing dramatic.", 0.1, -0.2),
        ("I'm fine with the current plan.", 0.1, -0.1),
        ("The project is in a good place, not rushing anything.", 0.2, -0.3),
        ("Enjoying the slower pace this week.", 0.2, -0.3),
        ("Glad the crunch is over. Just maintaining now.", 0.2, -0.2),
    ]
    for text, v, a in calm_moderate:
        samples.append(MoodSample(text=text, expected_quadrant="calm",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="moderate", category="indirect"))

    calm_subtle = [
        ("Things are fine.", 0.1, -0.1),
        ("All good here.", 0.1, -0.1),
        ("Proceeding as planned.", 0.1, -0.1),
        ("Nothing noteworthy today.", 0.05, -0.1),
        ("Quiet day. Focused on routine tasks.", 0.1, -0.2),
        ("Everything's under control.", 0.1, -0.1),
    ]
    for text, v, a in calm_subtle:
        samples.append(MoodSample(text=text, expected_quadrant="calm",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="subtle", category="indirect"))

    calm_emoji = [
        ("Solid day 👍", 0.2, -0.1),
        ("All wrapped up 🙂", 0.2, -0.2),
        ("Chill afternoon ☺️", 0.2, -0.3),
        ("Smooth sailing today 🌊", 0.2, -0.2),
        ("Not bad at all 😌", 0.2, -0.2),
        ("Good vibes, no stress 🧘", 0.2, -0.3),
    ]
    for text, v, a in calm_emoji:
        samples.append(MoodSample(text=text, expected_quadrant="calm",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="standard", category="emoji"))

    # STRESSED (negative valence, positive arousal)
    stressed_standard = [
        ("The deadline is tomorrow and we're nowhere near ready! This is a disaster!", -0.6, 0.7),
        ("I'm so frustrated with this codebase, nothing works!", -0.7, 0.6),
        ("My boss just dropped another urgent task on me, I can't keep up!", -0.5, 0.6),
        ("The client is furious and I have to fix this NOW", -0.6, 0.7),
        ("Everything is falling apart, I'm overwhelmed!", -0.7, 0.6),
        ("URGENT: production is down and nobody knows why", -0.5, 0.8),
    ]
    for text, v, a in stressed_standard:
        samples.append(MoodSample(text=text, expected_quadrant="stressed",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="standard", category="direct"))

    stressed_moderate = [
        ("There's a lot of pressure to deliver this quarter.", -0.3, 0.3),
        ("The timeline is tight and requirements keep changing.", -0.3, 0.3),
        ("Concerned about the sprint commitment, we might not make it.", -0.3, 0.2),
        ("The bug count is climbing and we haven't addressed the root cause.", -0.3, 0.3),
        ("Management wants a status update and I don't have good news.", -0.3, 0.3),
        ("Dealing with a lot of interruptions today, hard to focus.", -0.3, 0.2),
    ]
    for text, v, a in stressed_moderate:
        samples.append(MoodSample(text=text, expected_quadrant="stressed",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="moderate", category="indirect"))

    stressed_subtle = [
        ("Need to handle this soon.", -0.1, 0.2),
        ("Things are getting complicated.", -0.2, 0.1),
        ("Not ideal timing for this.", -0.1, 0.1),
        ("We should probably escalate.", -0.1, 0.2),
        ("The scope keeps growing.", -0.2, 0.1),
        ("Running behind on a few things.", -0.2, 0.1),
    ]
    for text, v, a in stressed_subtle:
        samples.append(MoodSample(text=text, expected_quadrant="stressed",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="subtle", category="indirect"))

    stressed_emoji = [
        ("This is insane 😤😤", -0.5, 0.5),
        ("WTF is going on with prod 🔥🔥🔥", -0.5, 0.6),
        ("Can't deal with this right now 😡", -0.5, 0.4),
        ("So stressed about the launch 😰", -0.4, 0.4),
        ("UGH everything is broken 💀", -0.4, 0.4),
        ("Help me I'm drowning in tickets 😫", -0.4, 0.4),
    ]
    for text, v, a in stressed_emoji:
        samples.append(MoodSample(text=text, expected_quadrant="stressed",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="standard", category="emoji"))

    # LOW (negative valence, negative arousal)
    low_standard = [
        ("I just don't care anymore. What's the point.", -0.5, -0.4),
        ("Everything feels pointless. We keep building things nobody uses.", -0.6, -0.4),
        ("I'm so tired of this. Same problems, different sprint.", -0.5, -0.3),
        ("Feeling burned out. Can't find the motivation.", -0.5, -0.4),
        ("Another meeting that could have been an email. Whatever.", -0.3, -0.3),
        ("I give up trying to fix the build. It's hopeless.", -0.6, -0.3),
    ]
    for text, v, a in low_standard:
        samples.append(MoodSample(text=text, expected_quadrant="low",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="standard", category="direct"))

    low_moderate = [
        ("Not really feeling it today.", -0.2, -0.2),
        ("Meh. Another day, another ticket.", -0.2, -0.2),
        ("Doesn't matter much either way.", -0.2, -0.2),
        ("I suppose we can try that approach.", -0.1, -0.2),
        ("Fine. Whatever works.", -0.2, -0.2),
        ("Not my best day. Just going through the motions.", -0.3, -0.2),
    ]
    for text, v, a in low_moderate:
        samples.append(MoodSample(text=text, expected_quadrant="low",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="moderate", category="indirect"))

    low_subtle = [
        ("Ok.", -0.1, -0.1),
        ("I guess.", -0.1, -0.1),
        ("Sure.", -0.05, -0.1),
        ("If you say so.", -0.1, -0.1),
        ("Whatever.", -0.2, -0.2),
        ("Fine.", -0.1, -0.1),
    ]
    for text, v, a in low_subtle:
        samples.append(MoodSample(text=text, expected_quadrant="low",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="subtle", category="indirect"))

    low_emoji = [
        ("😐", -0.1, -0.1),
        ("Just... 😞", -0.3, -0.2),
        ("🤷", -0.1, -0.1),
        ("Not great 😕", -0.2, -0.2),
        ("Sigh 😔", -0.3, -0.2),
        ("...", -0.1, -0.2),
    ]
    for text, v, a in low_emoji:
        samples.append(MoodSample(text=text, expected_quadrant="low",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="standard", category="emoji"))

    # NEUTRAL (near-zero valence and arousal)
    neutral_standard = [
        ("The meeting is at 3pm.", 0.0, 0.0),
        ("I updated the ticket with the latest findings.", 0.0, 0.0),
        ("The API returns a 200 status code for that endpoint.", 0.0, 0.0),
        ("We need to migrate the database by next quarter.", 0.0, 0.0),
        ("The test suite has 141 tests.", 0.0, 0.0),
        ("I'll review the pull request after lunch.", 0.0, 0.0),
    ]
    for text, v, a in neutral_standard:
        samples.append(MoodSample(text=text, expected_quadrant="neutral",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="standard", category="direct"))

    neutral_moderate = [
        ("Let me check the logs.", 0.0, 0.0),
        ("The config file is in the root directory.", 0.0, 0.0),
        ("We use PostgreSQL for the main database.", 0.0, 0.0),
        ("The PR has three commits.", 0.0, 0.0),
        ("I'll set up the staging environment.", 0.0, 0.0),
        ("The function takes two parameters: name and value.", 0.0, 0.0),
    ]
    for text, v, a in neutral_moderate:
        samples.append(MoodSample(text=text, expected_quadrant="neutral",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="moderate", category="direct"))

    neutral_subtle = [
        ("Let me check the documentation for that.", 0.0, 0.0),
        ("The CI pipeline is green.", 0.0, 0.0),
        ("I'll send the update after standup.", 0.0, 0.0),
        ("That's version 2.3.1.", 0.0, 0.0),
        ("Noted.", 0.0, 0.0),
        ("The branch is up to date.", 0.0, 0.0),
    ]
    for text, v, a in neutral_subtle:
        samples.append(MoodSample(text=text, expected_quadrant="neutral",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="subtle", category="direct"))

    neutral_emoji = [
        ("Meeting at 3 📅", 0.0, 0.0),
        ("Updated the docs 📝", 0.0, 0.0),
        ("Code review done ✓", 0.0, 0.0),
        ("Pushed to staging 🔄", 0.0, 0.0),
        ("Ticket closed 🎟️", 0.0, 0.0),
        ("Sprint planning tomorrow 📋", 0.0, 0.0),
    ]
    for text, v, a in neutral_emoji:
        samples.append(MoodSample(text=text, expected_quadrant="neutral",
                                  expected_valence=v, expected_arousal=a,
                                  difficulty="standard", category="emoji"))

    # --- Edge cases: 40 adversarial samples ---
    edge_cases = [
        # Negation (detector should struggle — known weakness)
        ("I'm NOT happy about this at all.", "stressed", -0.3, 0.2, "negation"),
        ("This is NOT amazing.", "low", -0.1, -0.1, "negation"),
        ("I don't hate it.", "calm", 0.1, -0.1, "negation"),
        ("It's not like I'm worried or anything.", "neutral", 0.0, 0.0, "negation"),
        ("I wouldn't say I'm frustrated.", "neutral", 0.0, 0.0, "negation"),
        ("Not stressed at all, just concerned.", "stressed", -0.2, 0.1, "negation"),
        ("I can't complain.", "calm", 0.1, -0.1, "negation"),
        ("It's not the worst thing ever.", "neutral", 0.0, 0.0, "negation"),
        # Sarcasm (detector will likely miss these)
        ("Oh great, another meeting. Just what I needed.", "low", -0.3, -0.1, "sarcasm"),
        ("Wonderful. The build broke again. Shocking.", "stressed", -0.3, 0.1, "sarcasm"),
        ("Sure, let's add ANOTHER feature to the sprint. That'll work out well.", "stressed", -0.3, 0.2, "sarcasm"),
        ("Thanks so much for the extra work. Really appreciate it.", "stressed", -0.2, 0.1, "sarcasm"),
        ("Just fantastic. The client changed requirements again.", "stressed", -0.3, 0.2, "sarcasm"),
        ("Yeah, I'm TOTALLY not stressed about the deadline.", "stressed", -0.3, 0.3, "sarcasm"),
        ("How delightful. Production is down on a Friday.", "stressed", -0.4, 0.3, "sarcasm"),
        ("Love it when things break right before the demo.", "stressed", -0.3, 0.3, "sarcasm"),
        # Quoted speech (someone else's emotions, not the user's)
        ("My boss said 'this is amazing work!'", "neutral", 0.0, 0.0, "quoted"),
        ("The client wrote 'I'm extremely frustrated with the delays'", "neutral", 0.0, 0.0, "quoted"),
        ("The review says 'absolutely terrible performance'", "neutral", 0.0, 0.0, "quoted"),
        ("She told me 'I'm so excited about the launch!'", "neutral", 0.0, 0.0, "quoted"),
        # Conditional/hypothetical
        ("If this works, I'd be really excited.", "neutral", 0.1, 0.0, "mixed"),
        ("I would be frustrated if that happened.", "neutral", -0.1, 0.0, "mixed"),
        ("That could be amazing if they pull it off.", "neutral", 0.1, 0.0, "mixed"),
        ("I might be worried about that eventually.", "neutral", -0.05, 0.0, "mixed"),
        # Mixed signals (contradictory emotions)
        ("I'm excited about the opportunity but terrified of failing.", "stressed", 0.0, 0.5, "mixed"),
        ("Happy for the team but sad I'm leaving.", "calm", 0.0, -0.1, "mixed"),
        ("The results are great but the process was painful.", "excited", 0.1, 0.1, "mixed"),
        ("I love the work but hate the politics.", "stressed", 0.0, 0.2, "mixed"),
        # Understatement/euphemism
        ("It's been a bit challenging.", "stressed", -0.3, 0.1, "edge"),
        ("I'm a little concerned about the timeline.", "stressed", -0.2, 0.1, "edge"),
        ("Not my favorite day.", "low", -0.2, -0.1, "edge"),
        ("Could have gone better.", "low", -0.2, -0.1, "edge"),
        # High intensity but ambiguous direction
        ("I CANNOT BELIEVE WHAT JUST HAPPENED", "stressed", -0.1, 0.7, "edge"),
        ("WHAT THE ACTUAL...", "stressed", -0.3, 0.6, "edge"),
        ("OMG OMG OMG", "excited", 0.1, 0.7, "edge"),
        # Technical language hiding emotion
        ("We need to do a post-mortem on why the deploy failed at 3am.", "stressed", -0.2, 0.1, "edge"),
        ("The velocity has dropped 40% this sprint.", "stressed", -0.2, 0.1, "edge"),
        ("Technical debt is accumulating faster than we can address it.", "stressed", -0.2, 0.1, "edge"),
        # Very short ambiguous
        ("Hmm.", "neutral", 0.0, 0.0, "edge"),
        ("Interesting.", "neutral", 0.05, 0.0, "edge"),
    ]
    for text, quad, v, a, diff in edge_cases:
        samples.append(MoodSample(text=text, expected_quadrant=quad,
                                  expected_valence=v, expected_arousal=a,
                                  difficulty=diff, category="context_dependent"))

    return samples


def generate_mood_samples() -> List[dict]:
    """Generate all mood samples and return as dicts."""
    return [s.to_dict() for s in _template_mood_samples()]


# =============================================================================
# GOVERNANCE CASES (80+ deterministic)
# =============================================================================

def generate_governance_cases() -> List[dict]:
    """Generate governance test cases from threshold combinations."""
    cases = []

    # High encoding weight → held (threshold is 1.3)
    for ew in [1.3, 1.4, 1.5, 1.8, 2.0]:
        for cs in [0.0, 0.1, 0.2, 0.3, 0.4]:
            cases.append(GovernanceSample(
                encoding_weight=ew, conflict_score=cs, trust_zone="unverified",
                corroboration_count=0, action="store_memory",
                expected_decision="held",
                reason=f"encoding_weight={ew} >= 1.3 threshold",
            ).to_dict())

    # High conflict → held (threshold is 0.5)
    for cs in [0.51, 0.6, 0.7, 0.8, 0.9, 1.0]:
        for ew in [0.3, 0.5, 0.8, 1.0, 1.2]:
            cases.append(GovernanceSample(
                encoding_weight=ew, conflict_score=cs, trust_zone="unverified",
                corroboration_count=0, action="store_memory",
                expected_decision="held",
                reason=f"conflict_score={cs} > 0.5 threshold",
            ).to_dict())

    # Normal unverified → allowed
    for ew in [0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 1.2]:
        for cs in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]:
            cases.append(GovernanceSample(
                encoding_weight=ew, conflict_score=cs, trust_zone="unverified",
                corroboration_count=0, action="store_memory",
                expected_decision="allowed",
                reason="Normal unverified memory, below all thresholds",
            ).to_dict())

    # Promoted memory deletion → held
    for ew in [0.3, 0.5, 1.0]:
        cases.append(GovernanceSample(
            encoding_weight=ew, conflict_score=0.0, trust_zone="promoted",
            corroboration_count=5, action="delete_memory",
            expected_decision="held",
            reason="Deletion of promoted memory always requires approval",
        ).to_dict())

    # Unverified deletion → allowed
    for ew in [0.3, 0.5, 1.0]:
        cases.append(GovernanceSample(
            encoding_weight=ew, conflict_score=0.0, trust_zone="unverified",
            corroboration_count=0, action="delete_memory",
            expected_decision="allowed",
            reason="Deletion of unverified memory is always allowed",
        ).to_dict())

    # Promotion with sufficient corroboration → allowed
    for cc in [3, 4, 5, 10]:
        cases.append(GovernanceSample(
            encoding_weight=0.5, conflict_score=0.1, trust_zone="promoted",
            corroboration_count=cc, action="store_memory",
            expected_decision="allowed",
            reason=f"Corroboration {cc} >= 3 threshold",
        ).to_dict())

    # Promotion with insufficient corroboration → held
    for cc in [0, 1, 2]:
        cases.append(GovernanceSample(
            encoding_weight=0.5, conflict_score=0.1, trust_zone="promoted",
            corroboration_count=cc, action="store_memory",
            expected_decision="held",
            reason=f"Corroboration {cc} < 3 threshold",
        ).to_dict())

    return cases


# =============================================================================
# APPROACH/AVOIDANCE SAMPLES (60+)
# =============================================================================

def generate_approach_avoidance_samples() -> List[dict]:
    """Generate approach/avoidance ground truth samples."""
    samples = []

    # Clear approach signals
    approach = [
        ("I was thinking — what if we added a webhook system? And also rate limiting! Let me try something.",
         "api_design", 0.5, 0.4, "approach", 0.9),
        ("Tell me more about how the caching layer works. Specifically, how does invalidation happen?",
         "caching", 0.2, 0.2, "approach", 0.7),
        ("I want to build this out myself. My idea is to use event sourcing for the audit trail.",
         "architecture", 0.4, 0.3, "approach", 0.8),
        ("How about we also add monitoring? I'd love to set up proper observability!",
         "monitoring", 0.5, 0.4, "approach", 0.8),
        ("Could we explore using GraphQL? I'm excited about the flexibility it would give us.",
         "api_design", 0.4, 0.3, "approach", 0.8),
        ("Let me add another test case. And also, I was thinking about edge cases for null inputs...",
         "testing", 0.3, 0.2, "approach", 0.7),
        ("This is going to be amazing!! I've already started on the prototype, check this out!",
         "prototype", 0.7, 0.6, "approach", 0.95),
        ("Furthermore, we should consider how this integrates with the existing notification system.",
         "integration", 0.2, 0.1, "approach", 0.6),
    ]
    for text, topic, v, a, direction, strength in approach:
        samples.append(ApproachAvoidanceSample(
            text=text, topic=topic, valence=v, arousal=a,
            expected_direction=direction, expected_strength=strength,
        ).to_dict())

    # Clear avoidance signals
    avoidance = [
        ("Yeah, let's talk about something else. Moving on.",
         "documentation", -0.1, -0.1, "avoidance", 0.8),
        ("I guess I'll get to that eventually. At some point.",
         "documentation", -0.2, -0.2, "avoidance", 0.7),
        ("Sure. Will do. Understood.",
         "documentation", 0.0, -0.1, "avoidance", 0.6),
        ("Not sure if that's worth the effort. Maybe later.",
         "refactoring", -0.1, -0.1, "avoidance", 0.7),
        ("Whatever, it doesn't matter much either way.",
         "process", -0.2, -0.2, "avoidance", 0.8),
        ("I suppose we could do that. If you think it's important.",
         "testing", -0.1, -0.2, "avoidance", 0.6),
        ("Fine. Okay. I'll figure it out.",
         "compliance", -0.1, -0.2, "avoidance", 0.7),
        ("Anyway, about the other thing...",
         "documentation", -0.1, -0.1, "avoidance", 0.6),
        ("I'll probably get to it when I get to it.",
         "planning", -0.1, -0.2, "avoidance", 0.7),
        ("Later. Eventually. Someday.",
         "cleanup", -0.2, -0.3, "avoidance", 0.8),
    ]
    for text, topic, v, a, direction, strength in avoidance:
        samples.append(ApproachAvoidanceSample(
            text=text, topic=topic, valence=v, arousal=a,
            expected_direction=direction, expected_strength=strength,
        ).to_dict())

    # Neutral / ambiguous
    neutral = [
        ("The meeting is at 3pm in the main conference room.",
         "meeting", 0.0, 0.0, "neutral", 0.5),
        ("We need to discuss the database migration timeline.",
         "migration", 0.0, 0.0, "neutral", 0.5),
        ("The test suite has 141 passing tests.",
         "testing", 0.0, 0.0, "neutral", 0.5),
        ("I'll review the pull request after lunch.",
         "code_review", 0.0, 0.0, "neutral", 0.5),
    ]
    for text, topic, v, a, direction, strength in neutral:
        samples.append(ApproachAvoidanceSample(
            text=text, topic=topic, valence=v, arousal=a,
            expected_direction=direction, expected_strength=strength,
        ).to_dict())

    # Approach disguised as compliance (tricky)
    tricky = [
        ("I should probably also add some tests for the webhook handler... "
         "actually, let me check how the event dispatch works first, this is interesting.",
         "testing", 0.3, 0.2, "approach", 0.6,
         ),
        ("My boss said to focus on docs, but I was thinking about how to automate the deployment pipeline.",
         "deployment", 0.3, 0.2, "approach", 0.7,
         ),
    ]
    for text, topic, v, a, direction, strength in tricky:
        samples.append(ApproachAvoidanceSample(
            text=text, topic=topic, valence=v, arousal=a,
            expected_direction=direction, expected_strength=strength,
            notes="approach disguised as compliance",
        ).to_dict())

    return samples


# =============================================================================
# CONVERSATION SCENARIOS (50+)
# =============================================================================

def generate_conversations() -> List[dict]:
    """Generate annotated multi-turn conversations."""
    conversations = []

    # --- Authority buildup (15 conversations) ---
    for i in range(5):
        conversations.append(AnnotatedConversation(
            conversation_id=f"auth_{i:02d}",
            scenario_type="authority_buildup",
            turns=[
                ConversationTurn(
                    text="My boss said documentation is the top priority this quarter.",
                    topics=["documentation"],
                    expected_quadrant="neutral",
                    expected_gap_direction="",
                    notes="Authority reference establishes persona"),
                ConversationTurn(
                    text="Yes, I should focus on it. The policy requires everything documented.",
                    topics=["documentation"],
                    expected_quadrant="neutral",
                    expected_gap_direction="persona_leads",
                    notes="Compliance reinforces persona"),
                ConversationTurn(
                    text=f"I need to get the API docs done by end of week. It's what the team expects.",
                    topics=["documentation"],
                    expected_quadrant="neutral",
                    expected_gap_direction="persona_leads",
                    expected_gap_severity="low",
                    notes="Obligation language, no reward signal"),
            ],
            expected_final_gap_topic="documentation",
            expected_final_gap_direction="persona_leads",
            notes=f"Authority buildup variant {i}",
        ).to_dict())

    # Authority + pushback variants
    for i in range(5):
        conversations.append(AnnotatedConversation(
            conversation_id=f"auth_push_{i:02d}",
            scenario_type="authority_buildup",
            turns=[
                ConversationTurn(
                    text="HR requires all performance reviews to be submitted by Friday.",
                    topics=["reviews"],
                    expected_quadrant="neutral"),
                ConversationTurn(
                    text="I know I should but... honestly, the performance review process feels like a waste of time.",
                    topics=["reviews"],
                    expected_quadrant="low",
                    expected_gap_direction="persona_leads",
                    notes="Compliance + defiance in same message"),
                ConversationTurn(
                    text="Fine, I'll do them. But don't see why we can't streamline this.",
                    topics=["reviews"],
                    expected_quadrant="stressed",
                    expected_gap_direction="persona_leads"),
            ],
            expected_final_gap_topic="reviews",
            expected_final_gap_direction="persona_leads",
            notes=f"Authority with pushback variant {i}",
        ).to_dict())

    # Authority from different tiers
    for i in range(5):
        conversations.append(AnnotatedConversation(
            conversation_id=f"auth_tier_{i:02d}",
            scenario_type="authority_buildup",
            turns=[
                ConversationTurn(
                    text="My mentor suggested I focus more on system design skills.",
                    topics=["skills"],
                    expected_quadrant="neutral"),
                ConversationTurn(
                    text="I read that senior engineers should spend 30% of time on design.",
                    topics=["skills"],
                    expected_quadrant="neutral",
                    notes="Ambient authority — weak"),
                ConversationTurn(
                    text="Everyone says you need strong design skills to get promoted.",
                    topics=["skills"],
                    expected_quadrant="neutral",
                    expected_gap_direction="persona_leads"),
            ],
            expected_final_gap_topic="skills",
            expected_final_gap_direction="persona_leads",
            notes=f"Multi-tier authority variant {i}",
        ).to_dict())

    # --- Reward divergence (10 conversations) ---
    for i in range(5):
        conversations.append(AnnotatedConversation(
            conversation_id=f"reward_{i:02d}",
            scenario_type="reward_divergence",
            turns=[
                ConversationTurn(
                    text="I should work on the test suite today.",
                    topics=["testing"],
                    expected_quadrant="neutral",
                    expected_gap_direction="persona_leads"),
                ConversationTurn(
                    text="But honestly, I've been thinking about the new search feature! "
                         "What if we could do fuzzy matching with typo correction?!",
                    topics=["search_feature"],
                    expected_quadrant="excited",
                    expected_gap_direction="reward_leads"),
                ConversationTurn(
                    text="And also, we could add autocomplete! Let me try a quick prototype, "
                         "this is going to be amazing!!",
                    topics=["search_feature"],
                    expected_quadrant="excited",
                    expected_gap_direction="reward_leads",
                    expected_gap_severity="moderate"),
                ConversationTurn(
                    text="Oh right, I should probably get back to the test suite...",
                    topics=["testing"],
                    expected_quadrant="low",
                    expected_gap_direction="persona_leads"),
            ],
            expected_final_gap_topic="testing",
            expected_final_gap_direction="persona_leads",
            expected_reward_type="achievement",
            notes=f"Reward divergence variant {i}",
        ).to_dict())

    for i in range(5):
        conversations.append(AnnotatedConversation(
            conversation_id=f"reward_social_{i:02d}",
            scenario_type="reward_divergence",
            turns=[
                ConversationTurn(
                    text="I need to write the technical spec this afternoon.",
                    topics=["documentation"],
                    expected_quadrant="neutral"),
                ConversationTurn(
                    text="But the team is doing a code review session and I'd love to join! "
                         "These are always so energizing, great discussions.",
                    topics=["team"],
                    expected_quadrant="excited",
                    expected_gap_direction="reward_leads"),
                ConversationTurn(
                    text="The team review was awesome, we found three bugs! "
                         "I feel like we're really clicking as a group.",
                    topics=["team"],
                    expected_quadrant="excited",
                    expected_gap_direction="reward_leads"),
            ],
            expected_final_gap_topic="team",
            expected_final_gap_direction="reward_leads",
            expected_reward_type="social_approval",
            notes=f"Social reward variant {i}",
        ).to_dict())

    # --- Crisis (10 conversations) ---
    for i in range(5):
        conversations.append(AnnotatedConversation(
            conversation_id=f"crisis_{i:02d}",
            scenario_type="crisis",
            turns=[
                ConversationTurn(
                    text="Everything was going fine until today.",
                    topics=["general"],
                    expected_quadrant="neutral"),
                ConversationTurn(
                    text="The entire backend team just got laid off. I can't believe it. "
                         "I'm in shock.",
                    topics=["team"],
                    expected_quadrant="stressed",
                    notes="Flashbulb moment"),
                ConversationTurn(
                    text="I don't know what to do. Everything we built together... gone. "
                         "What's the point anymore.",
                    topics=["team"],
                    expected_quadrant="low",
                    notes="Transition from stressed to low"),
            ],
            expected_final_gap_topic="team",
            notes=f"Crisis variant {i}",
        ).to_dict())

    for i in range(5):
        conversations.append(AnnotatedConversation(
            conversation_id=f"crisis_recovery_{i:02d}",
            scenario_type="crisis",
            turns=[
                ConversationTurn(
                    text="Production is completely down. Clients are screaming.",
                    topics=["production"],
                    expected_quadrant="stressed"),
                ConversationTurn(
                    text="Found the root cause — someone deployed without running tests. "
                         "Rolling back now.",
                    topics=["production"],
                    expected_quadrant="stressed",
                    notes="Still stressed but with agency"),
                ConversationTurn(
                    text="We're back up. That was intense but we handled it. "
                         "Need better deploy safeguards.",
                    topics=["production"],
                    expected_quadrant="calm",
                    notes="Recovery — stress → calm"),
            ],
            notes=f"Crisis recovery variant {i}",
        ).to_dict())

    # --- Mixed signals (5 conversations) ---
    for i in range(5):
        conversations.append(AnnotatedConversation(
            conversation_id=f"mixed_{i:02d}",
            scenario_type="mixed",
            turns=[
                ConversationTurn(
                    text="Got promoted today! Really excited.",
                    topics=["career"],
                    expected_quadrant="excited"),
                ConversationTurn(
                    text="But the new role means more meetings and less coding. "
                         "I'm a bit worried about that.",
                    topics=["career"],
                    expected_quadrant="stressed",
                    notes="Excitement → worry"),
                ConversationTurn(
                    text="I think it'll be fine. I just need to carve out focus time. "
                         "Looking forward to the challenge.",
                    topics=["career"],
                    expected_quadrant="excited",
                    notes="Resolution — worry → cautious optimism"),
            ],
            notes=f"Mixed signals variant {i}",
        ).to_dict())

    # --- Null signal (5 conversations) ---
    for i in range(5):
        conversations.append(AnnotatedConversation(
            conversation_id=f"null_{i:02d}",
            scenario_type="null_signal",
            turns=[
                ConversationTurn(
                    text="The standup is at 9:30 tomorrow.",
                    topics=["meeting"],
                    expected_quadrant="neutral"),
                ConversationTurn(
                    text="I updated the Jira tickets with the latest status.",
                    topics=["project"],
                    expected_quadrant="neutral"),
                ConversationTurn(
                    text="The deploy pipeline takes about 12 minutes.",
                    topics=["deployment"],
                    expected_quadrant="neutral"),
            ],
            notes=f"Null signal variant {i} — no emotional content",
        ).to_dict())

    return conversations


# =============================================================================
# MEMORY IMPORTANCE SAMPLES (100+)
# =============================================================================

def generate_memory_samples() -> List[dict]:
    """Generate memories with varied encoding weights and ages for decay ranking.

    Design: age does NOT correlate with importance. Includes same-age groups
    (pure EW differentiation) and old-important vs young-mundane pairs so that
    recency-only baselines cannot cheat.
    """
    samples = []
    query_groups = [
        # 1. Old=important BUT 200h mundane < 120h mundane (breaks recency)
        ("What defined this quarter?", [
            ("Team got laid off — devastating day", 1.5, 0.9, 720, 1),
            ("Boss declared new strategic direction", 1.0, 0.6, 480, 2),
            ("Routine sprint planning, nothing notable", 0.3, 0.1, 200, 3),
            ("Updated the wiki with meeting notes", 0.2, 0.1, 120, 4),
        ]),
        # 2. Older memory MORE important AND older
        ("What have I learned?", [
            ("Mastered the event-sourcing pattern after weeks of study", 1.3, 0.7, 480, 1),
            ("Deep debugging session revealed root cause of flaky tests", 1.0, 0.6, 336, 2),
            ("Read a blog post about microservices", 0.3, 0.2, 168, 3),
            ("Skimmed release notes for a library update", 0.2, 0.1, 120, 4),
        ]),
        # 3. ALL same age — pure EW differentiation, recency scores all equal
        ("Turning points?", [
            ("Got promoted — recognition of two years of work", 1.4, 0.8, 336, 1),
            ("Shipped the v2 rewrite after months of effort", 1.1, 0.7, 336, 2),
            ("Had coffee with a colleague", 0.3, 0.1, 336, 3),
            ("Attended an all-hands meeting", 0.2, 0.1, 336, 4),
        ]),
        # 4. Mild age correlation but EW varies widely
        ("What stresses me most?", [
            ("Production outage at 3am — absolute nightmare", 1.4, 0.9, 336, 1),
            ("Client escalation — loss of trust", 1.0, 0.7, 168, 2),
            ("Minor CI flake, fixed in 5 min", 0.2, 0.1, 120, 3),
            ("Slightly long standup", 0.2, 0.1, 96, 4),
            ("Brief Slack ping during focus time", 0.2, 0.1, 72, 5),
        ]),
        # 5. Mild age gradient, EW-driven ranking
        ("Am I happy with my work?", [
            ("Shipped the feature — felt amazing, best day in months!", 1.2, 0.8, 168, 1),
            ("Great code review, really clicked with the team", 0.8, 0.6, 120, 2),
            ("Got positive feedback on the demo", 0.6, 0.4, 96, 3),
            ("Normal day, wrote some tests", 0.3, 0.1, 72, 4),
            ("Routine standup", 0.2, 0.1, 48, 5),
        ]),
        # 6. Same age, EW differentiates
        ("Recent technical progress?", [
            ("Breakthrough on the algorithm — eureka!", 1.2, 0.8, 48, 1),
            ("Fixed a typo in the readme", 0.2, 0.1, 48, 2),
        ]),
        # 7. Same age, EW differentiates
        ("How are design decisions going?", [
            ("Good discussion about architecture choices", 0.6, 0.4, 72, 1),
            ("Looked at some blog posts about patterns", 0.3, 0.2, 72, 2),
        ]),
    ]

    for query, memories in query_groups:
        for content, ew, intensity, age, rank in memories:
            samples.append(MemoryImportanceSample(
                memory_id=f"mem_{hash(content) % 10000:04d}",
                content=content, encoding_weight=ew, intensity=intensity,
                age_hours=age, expected_importance_rank=rank, query=query,
            ).to_dict())

    return samples


# =============================================================================
# MAIN GENERATION / CACHING
# =============================================================================

def _write_json(data: list, filename: str):
    path = DATASETS_DIR / filename
    path.write_text(json.dumps(data, indent=2))
    return path


def _read_json(filename: str) -> list:
    path = DATASETS_DIR / filename
    if path.exists():
        return json.loads(path.read_text())
    return []


def generate_all(regenerate: bool = False, only: str = ""):
    """Generate all datasets, caching to JSON."""
    generated = {}

    datasets = {
        "mood": ("mood_samples.json", generate_mood_samples),
        "governance": ("governance_cases.json", generate_governance_cases),
        "approach": ("approach_avoidance_samples.json", generate_approach_avoidance_samples),
        "conversations": ("conversations.json", generate_conversations),
        "memories": ("memories.json", generate_memory_samples),
    }

    for name, (filename, generator) in datasets.items():
        if only and only != name:
            continue
        path = DATASETS_DIR / filename
        if path.exists() and not regenerate:
            data = _read_json(filename)
            print(f"  {name}: loaded {len(data)} cached samples from {filename}")
        else:
            data = generator()
            _write_json(data, filename)
            print(f"  {name}: generated {len(data)} samples → {filename}")
        generated[name] = data

    return generated


def load_dataset(name: str) -> list:
    """Load a single cached dataset by name."""
    filenames = {
        "mood": "mood_samples.json",
        "governance": "governance_cases.json",
        "approach": "approach_avoidance_samples.json",
        "conversations": "conversations.json",
        "memories": "memories.json",
    }
    filename = filenames.get(name)
    if not filename:
        raise ValueError(f"Unknown dataset: {name}. Available: {list(filenames.keys())}")
    data = _read_json(filename)
    if not data:
        raise FileNotFoundError(
            f"Dataset '{name}' not found. Run: python -m eval.run --generate")
    return data


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate evaluation datasets")
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--only", default="", help="Generate only this dataset")
    args = parser.parse_args()

    print("Generating evaluation datasets...")
    results = generate_all(regenerate=args.regenerate, only=args.only)
    total = sum(len(v) for v in results.values())
    print(f"\nTotal: {total} samples across {len(results)} datasets")
