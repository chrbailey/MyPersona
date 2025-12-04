# Solving the Labeled Data Problem

## The Problem

Traditional ML needs labeled data:
- "This response was helpful" (explicit label)
- "User was stressed when they sent this" (manual annotation)
- "The real intent behind this query was X" (expert judgment)

**We can't ask veterans to label their own data.** That defeats the purpose - reducing cognitive load.

## TikTok's Solution: Behavior IS the Label

TikTok never asks "did you like this video?" - they infer it:

| Implicit Signal | What It Means |
|-----------------|---------------|
| Watch completion | Interest |
| Rewatch | High interest |
| Quick scroll | Disinterest |
| 2.3s hesitation | Conflicted interest |
| Time before next action | Processing time |

**Watch time is their ground truth.** No explicit labels needed.

## MyPersona's Implicit Labels

We use the same principle. After every response, we collect:

### 1. Response Acceptance Signals

```
POSITIVE IMPLICIT LABELS:
- Continued engagement (kept using the app)
- Quick follow-up action (response was understood)
- No correction/clarification needed
- Session continuation
- Relaxation in biometrics after response

NEGATIVE IMPLICIT LABELS:
- Quick dismiss/close
- Immediate re-query (response didn't help)
- Typing a correction ("No, I meant...")
- Frustration signals (repeated taps, sighs)
- Biometric stress increase after response
```

### 2. Outcome-Based Labels

```python
class ImplicitLabelGenerator:
    def evaluate_response(self, response_sent_at: datetime):
        """Generate implicit label from post-response behavior"""

        window = 60  # seconds after response

        # POSITIVE signals
        continued = self.user_continued_session(window)
        followed_up = self.user_took_action(window)
        no_correction = not self.user_corrected_query(window)
        biometric_stable = self.stress_level_stable_or_decreased(window)

        # NEGATIVE signals
        dismissed = self.response_dismissed_quickly()
        re_queried = self.same_topic_re_queried(window)
        frustration = self.frustration_detected(window)

        # Calculate implicit satisfaction score
        positive_signals = sum([continued, followed_up, no_correction, biometric_stable])
        negative_signals = sum([dismissed, re_queried, frustration])

        # Score: -1 to +1
        score = (positive_signals - (negative_signals * 2)) / 4  # Weight negative 2x
        return score
```

### 3. Self-Calibrating Baselines

**No external data needed** - each user calibrates themselves:

```
WEEK 1: CALIBRATION PERIOD
- Collect baseline heart rate at different times
- Collect baseline typing speed and error rate
- Collect baseline scroll patterns
- Collect baseline response preferences (length, style)

AFTER WEEK 1: DEVIATION DETECTION
- Compare current signals to THEIR baseline
- HR 20% above THEIR normal = stress signal
- Typing 30% slower than THEIR normal = cognitive load
- Scroll 50% faster than THEIR normal = disinterest

NO POPULATION-LEVEL DATA NEEDED
- We don't compare to "average user"
- We compare to THIS user's own patterns
- Privacy preserved - nothing leaves device
```

### 4. The Feedback Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTINUOUS LEARNING LOOP                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Query ──► Context Inference ──► Response ──► Behavior     │
│       │                                              │          │
│       │                                              │          │
│       └───────────────── IMPLICIT LABEL ◄───────────┘          │
│                              │                                  │
│                              ▼                                  │
│                    Model Update (On-Device)                     │
│                                                                  │
│  If response led to:                                            │
│    - Continued engagement → Reinforce context interpretation    │
│    - Quick dismiss → Reduce confidence in that inference        │
│    - Re-query → Context was wrong, adjust                       │
│    - Frustration → Flag this pattern as problematic             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation: RLUF (Reinforcement Learning from User Feedback)

Based on [Meta's RLUF research](https://arxiv.org/html/2505.14946):

```python
class RLUFTrainer:
    """Reinforcement Learning from User Feedback"""

    def __init__(self):
        self.reward_model = UserSignalRewardModel()
        self.policy = ContextInferencePolicy()

    def collect_implicit_feedback(self, response, post_behavior):
        """
        Binary signals we can collect:
        - Did user continue? (1/0)
        - Did user re-query? (1/0)
        - Did user show frustration? (1/0)
        - Did biometrics improve? (1/0)
        """
        reward = self.reward_model.predict(response, post_behavior)
        return reward

    def update_policy(self, context, response, reward):
        """Update context inference based on implicit feedback"""
        if reward > 0:
            # Response worked - reinforce this context interpretation
            self.policy.reinforce(context, strength=reward)
        else:
            # Response failed - weaken this interpretation
            self.policy.weaken(context, strength=abs(reward))

            # If strongly negative, consider this a WARNING signal
            if reward < -0.5:
                self.policy.add_warning(context)

            # If very strongly negative, consider TRAUMA tier
            if reward < -0.8:
                self.policy.add_trauma_avoidance(context)
```

## The Minimum Viable Signal Set

We don't need complex sensors. The minimum viable implicit feedback:

| Signal | How to Collect | What It Tells Us |
|--------|----------------|------------------|
| **Time to next action** | Timestamp diff | Understanding vs confusion |
| **Re-query same topic** | Text similarity | Response didn't help |
| **Session length** | App analytics | Overall satisfaction |
| **Response dismiss speed** | Touch event | Response relevance |
| **Input error rate** | Keystroke tracking | Cognitive load / frustration |

**That's 5 signals.** All collectable without special hardware.

## Advanced Signals (Optional)

If the user has a wearable:

| Signal | Source | What It Tells Us |
|--------|--------|------------------|
| **HR change post-response** | Watch | Stress relief vs increase |
| **HRV trend** | Watch | Calm vs anxious state |
| **Movement after response** | Phone accelerometer | Action taken or frozen |

## Cold Start Problem

What about new users with no baseline?

### Solution 1: Conservative Defaults
- Assume stress until proven otherwise
- Default to brief responses
- Increase verbosity only when explicitly requested

### Solution 2: Archetype Priors
- If veteran with TBI flag → Start with cognitive support mode
- If elderly → Start with simple, clear language
- If indicated physical limitation → Minimize input requirements

### Solution 3: Quick Calibration
- First 3 interactions: Ask brief preference questions
  - "Would you prefer shorter or longer responses?"
  - "Morning or evening person?"
- Build on these priors, refine with implicit feedback

## Privacy Guarantee

```
ALL LEARNING HAPPENS ON-DEVICE

Raw signals → Never leave device
Implicit labels → Never leave device
Model updates → Never leave device
Baseline data → Never leave device

What could theoretically be shared (but isn't by default):
- Aggregate, anonymized patterns (opt-in only)
- Model weight updates (federated learning, if opted in)

What is NEVER shared:
- Individual queries
- Biometric data
- Location data
- Any identifying information
```

## Why This Works for Veterans

1. **Zero extra burden**: No rating requests, no surveys, no "was this helpful?"
2. **Adapts to bad days**: If everything triggers frustration signals, system backs off
3. **Respects cognitive limits**: Learning from behavior, not requiring explanation
4. **Handles inconsistency**: TBI means some days are harder - system adapts in real-time
5. **Physical limitation aware**: Typing difficulty is itself a signal, not a failure

## The Math

```python
# Implicit satisfaction score
def calculate_implicit_satisfaction(post_response_behavior):
    """
    -1.0 = Strongly negative (avoid this in future)
    0.0 = Neutral (no strong signal)
    +1.0 = Strongly positive (do more of this)
    """

    # Positive signals (each 0 or 1)
    continued = behavior.session_continued
    acted = behavior.took_action_within_60s
    no_correction = not behavior.re_queried_similar
    relaxed = behavior.biometric_stress_decreased

    # Negative signals (each 0 or 1)
    dismissed = behavior.dismissed_within_2s
    re_asked = behavior.re_queried_same_topic
    frustrated = behavior.frustration_signals_detected
    stress_increased = behavior.biometric_stress_increased

    # Calculate score
    positive = continued + acted + no_correction + relaxed  # max 4
    negative = dismissed + re_asked + frustrated + stress_increased  # max 4

    # Asymmetric: negative signals weighted 1.5x
    score = (positive - (negative * 1.5)) / 4

    return max(-1.0, min(1.0, score))
```

---

## Summary

**We don't need labeled data.**

TikTok proved you can build the most effective recommendation system in history using only implicit signals. We apply the same principle:

- Behavior after response = implicit label
- User's own history = calibration baseline
- On-device learning = privacy preserved
- Asymmetric weighting = negative signals matter more

**The user never has to tell us anything. We learn by watching what works.**

---

*Sources:*
- [RLUF: Reinforcement Learning from User Feedback](https://arxiv.org/html/2505.14946)
- [TikTok Algorithm Research](https://www.washington.edu/news/2024/04/24/tiktok-black-box-algorithm-and-design-user-behavior-recommendation/)
- [Implicit vs Explicit Feedback](https://arxiv.org/html/2502.09869v1)
- [Self-Supervised Learning for Recommendation](https://dl.acm.org/doi/10.1145/3746280)
