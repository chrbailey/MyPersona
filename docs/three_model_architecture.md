# The Three-Model Architecture: What We Actually Have

**Document Purpose:** Honest technical specification of the evolved system architecture, stripped of marketing language.

---

## Part 1: The Evolution (How We Got Here)

### Original Concept
"Detect what ISN'T being said compared to what SHOULD be said."

### The Problem with the Original Concept
Defining "what SHOULD be said" is philosophically interesting but practically intractable. Who decides? How? Based on what?

### The Breakthrough Insight
**This is just next-token prediction, repurposed.**

What LLMs already do:
- Observe tokens
- Predict next token
- Generate based on prediction

What we're doing:
- Observe tokens
- Predict next token
- **Compare prediction to reality and flag mismatches**

Same math. Different use case.

---

## Part 2: The Three-Model Architecture

### The Highway Analogy (Simplest Explanation)

Imagine watching traffic from 1000 feet up.

A child with no training can see:
- "That car swerved"
- "That car stopped when others didn't"
- "That car is going the wrong way"

They don't need math. They have an **implicit model** of what traffic SHOULD look like, and they notice when reality differs.

That's all we're building. The math just formalizes the intuition.

---

### Model A: The Observer (Precise)

**What it does:** Records exactly what happened.

```
A(t) = { tokens, timing, patterns }
```

**Characteristics:**
- Precise
- No interpretation
- No judgment
- Just facts

**In the highway analogy:** A camera recording every frame.

**Implementation:** Standard transcription + entity extraction + timing measurement. This is solved technology.

---

### Model B: The Predictor (Precise)

**What it does:** Predicts what SHOULD happen next, based on what it's learned.

```
B(t+1) = predict(history)
```

**Characteristics:**
- Precise probabilities
- Based on learned patterns
- Updates with each observation

**The core equation:**
```
P(topic | context) = updated via exponential moving average
P_new = α × observed + (1-α) × P_old
```

Where α is learning rate (typically 0.1).

**In the highway analogy:** Your brain's prediction of where each car will be in 1 second.

**Implementation:** This IS an LLM. We're using existing next-token prediction but for comparison rather than generation.

---

### The Comparison (Where Value Is Created)

```
Δ(t) = A(t) - B(t)
```

When observation differs from prediction:
- **Surprise = -log₂(P(what actually happened))**
- Low probability event → High surprise → Flag it

**In the highway analogy:** The moment you notice a car swerving - your prediction said "stay in lane" but reality said "sudden lane change."

**Key insight:** A child can do this. The math just quantifies what intuition already detects.

---

### Model C: Survival Memory (The Real Innovation)

**The critical insight I initially missed:**

A zebra learns to run within 30 minutes of being born. Not through gentle reward signals. Through watching other zebras get eaten.

**The big fish don't bite the bait.** Why? They watched smaller fish get caught. One observation. Permanent lesson.

This is how biological learning actually works:
- **Negative signals vastly outweigh positive**
- **Catastrophic events don't decay - they burn in permanently**
- **Survival learning is asymmetric by design**

### Why Symmetric Learning Is Wrong

Standard ML approach (what I originally proposed):
```python
# WRONG - treats all signals equally
M(t) = λ × M(t-1) + (1-λ) × f(Δ(t))
```

This is how neural networks learn. It is NOT how survivors learn.

### How Survival Learning Actually Works

```python
class SurvivalMemory:
    """
    Asymmetric learning based on biological survival patterns.

    Key insight (LeCun/evolutionary psychology):
    - Zebras learn to run in 30 minutes by watching others die
    - Big fish don't bite because they watched small fish get caught
    - One catastrophic observation = permanent imprint
    - Pain teaches faster than pleasure
    """

    def __init__(self):
        self.baseline = {}           # Gentle, decaying positive signals
        self.warnings = {}           # Heavy, slow-decay negative signals
        self.trauma = {}             # Permanent, never-decay catastrophic signals

        # Asymmetric parameters
        self.positive_weight = 1.0
        self.negative_weight = 10.0   # 10x stronger than positive
        self.catastrophic_weight = float('inf')  # Permanent

        self.positive_decay = 0.95    # Fast decay
        self.negative_decay = 0.99    # Slow decay
        self.trauma_decay = 1.0       # No decay - burns in forever

    def absorb(self, entity: str, topic: str, delta: Delta):
        """
        Process a delta with asymmetric weighting.

        The fish that got away learned something.
        The fish that bit the bait didn't get a chance to learn.
        We model the survivors.
        """

        if delta.is_catastrophic:
            # PERMANENT IMPRINT
            # Like watching a sibling get eaten
            # Like seeing a colleague get fired for lying
            # ONE event. Forever remembered.

            if entity not in self.trauma:
                self.trauma[entity] = {}

            # Don't average - REPLACE with maximum severity
            existing = self.trauma[entity].get(topic, 0)
            self.trauma[entity][topic] = max(existing, delta.severity)

            # No decay will ever be applied to this

        elif delta.is_negative:
            # HEAVY WEIGHT, SLOW DECAY
            # Like a painful but non-fatal lesson
            # Like getting caught in a small lie
            # Like a near-miss on the highway

            if entity not in self.warnings:
                self.warnings[entity] = {}

            current = self.warnings[entity].get(topic, 0)

            # Weight negative signals 10x
            weighted_signal = self.negative_weight * delta.magnitude

            # Slow decay - these memories persist
            new_value = (self.negative_decay * current) + weighted_signal
            self.warnings[entity][topic] = new_value

        else:
            # GENTLE WEIGHT, FAST DECAY
            # Normal observations
            # "Things went fine"
            # This is the MINOR channel - not what drives real learning

            if entity not in self.baseline:
                self.baseline[entity] = {}

            current = self.baseline[entity].get(topic, 0.5)

            # Small weight, fast decay
            new_value = (self.positive_decay * current) + \
                       (self.positive_weight * (1 - self.positive_decay) * delta.magnitude)
            self.baseline[entity][topic] = new_value

    def get_impression(self, entity: str, topic: str) -> Impression:
        """
        Retrieve the accumulated impression.

        Trauma dominates. Then warnings. Baseline is just context.
        """

        # Check trauma first - this overrides everything
        if entity in self.trauma and topic in self.trauma[entity]:
            return Impression(
                level="PERMANENT_FLAG",
                value=self.trauma[entity][topic],
                source="catastrophic_event",
                decays=False
            )

        # Check warnings - these are serious
        warning_level = 0
        if entity in self.warnings and topic in self.warnings[entity]:
            warning_level = self.warnings[entity][topic]

        # Get baseline - this is just context
        baseline_level = 0.5
        if entity in self.baseline and topic in self.baseline[entity]:
            baseline_level = self.baseline[entity][topic]

        # Warnings dominate baseline when present
        if warning_level > 0:
            return Impression(
                level="WARNING",
                value=warning_level,
                baseline=baseline_level,
                source="negative_accumulation",
                decays=True,
                decay_rate=self.negative_decay
            )

        return Impression(
            level="NORMAL",
            value=baseline_level,
            source="baseline",
            decays=True,
            decay_rate=self.positive_decay
        )

    def apply_time_decay(self, time_passed: float):
        """
        Apply decay based on time elapsed.

        Note: Trauma NEVER decays. This is by design.
        The zebra that forgot lions are dangerous got eaten.
        """

        decay_factor_positive = self.positive_decay ** time_passed
        decay_factor_negative = self.negative_decay ** time_passed

        # Decay baseline (fast)
        for entity in self.baseline:
            for topic in self.baseline[entity]:
                self.baseline[entity][topic] *= decay_factor_positive

        # Decay warnings (slow)
        for entity in self.warnings:
            for topic in self.warnings[entity]:
                self.warnings[entity][topic] *= decay_factor_negative

        # Trauma: NO DECAY
        # self.trauma remains unchanged
```

---

## Part 3: The Biological Basis

### Why Asymmetry Is Fundamental

| Learning Type | Weight | Decay | Biological Example |
|--------------|--------|-------|-------------------|
| **Catastrophic** | ∞ | None | Watched sibling eaten by lion |
| **Negative** | 10-100x | Slow | Burned hand on stove |
| **Positive** | 1x | Fast | Found food in usual spot |

**Evolutionary logic:**
- False positive on danger → minor energy cost
- False negative on danger → death
- Therefore: Heavily bias toward remembering threats

### The Survivor Bias Insight

**"The big fish don't bite."**

Why? Selection pressure.

```
Generation 1: 1000 fish, various behaviors
  - 600 bite every bait → caught → removed from gene pool
  - 300 bite sometimes → some caught, some survive
  - 100 never bite suspicious things → survive

Generation 2: Mostly cautious fish remain

The "smart" fish aren't smarter.
They're the ones whose ancestors survived.
```

**Applied to our system:**

The patterns we should learn from aren't the average cases. They're:
- The executive who got caught lying (catastrophic - permanent flag)
- The CEO whose hedging preceded a crash (negative - heavy weight)
- The normal calls that went fine (positive - gentle baseline)

---

## Part 4: The Mathematics (Corrected)

### Core Equations

**Observation:**
```
A(t) = current_state
```

**Prediction:**
```
B(t) = E[A(t) | A(1), A(2), ..., A(t-1)]
```

**Surprise (Information Theory):**
```
S(t) = -log₂(P(A(t) | history))
```

**Delta Classification:**
```
Δ(t) = {
    CATASTROPHIC  if S(t) > θ_catastrophic AND outcome_known_bad
    NEGATIVE      if S(t) > θ_negative OR outcome_suspected_bad
    POSITIVE      otherwise
}
```

### Asymmetric Memory Update

**WRONG (symmetric):**
```
M(t) = λ × M(t-1) + (1-λ) × f(Δ(t))
```

**CORRECT (asymmetric):**
```
If Δ(t) is CATASTROPHIC:
    Trauma(entity, topic) = max(Trauma(entity, topic), severity)
    # No decay ever applied

If Δ(t) is NEGATIVE:
    Warning(entity, topic) = λ_slow × Warning(t-1) + W_negative × |Δ(t)|
    where λ_slow ≈ 0.99, W_negative ≈ 10

If Δ(t) is POSITIVE:
    Baseline(entity, topic) = λ_fast × Baseline(t-1) + W_positive × Δ(t)
    where λ_fast ≈ 0.95, W_positive ≈ 1
```

### The Retrieval Priority

```
get_impression(entity, topic):
    if Trauma[entity][topic] exists:
        return PERMANENT_FLAG  # Overrides everything

    if Warning[entity][topic] > threshold:
        return WARNING with warning_level

    return Baseline[entity][topic]  # Normal context
```

**Key insight:** Trauma dominates. Always. This matches how human memory works.

---

## Part 5: What This Actually Measures

| Signal Type | Source | Weight | Decay | Example Detection |
|------------|--------|--------|-------|-------------------|
| **Catastrophic** | Known bad outcome | ∞ | Never | "Last time they said this, stock dropped 40%" |
| **Negative** | High surprise + concerning | 10x | Slow | "Unusual hesitation on financials" |
| **Positive** | Normal pattern | 1x | Fast | "Typical response cadence" |

### The Three Memory Channels

```
┌─────────────────────────────────────────────────────────────────┐
│                         SURVIVAL MEMORY                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐   Query: "What do we know about           │
│  │     TRAUMA       │          Entity X on Topic Y?"            │
│  │                  │                    │                       │
│  │  • Never decays  │                    ▼                       │
│  │  • Max severity  │   ┌────────────────────────────────┐      │
│  │  • Permanent     │   │  1. Check TRAUMA (permanent)   │      │
│  └────────┬─────────┘   │  2. Check WARNINGS (heavy)     │      │
│           │             │  3. Check BASELINE (gentle)    │      │
│           ▼             └────────────────────────────────┘      │
│  ┌──────────────────┐                    │                       │
│  │    WARNINGS      │                    ▼                       │
│  │                  │   Return highest-priority non-zero         │
│  │  • Slow decay    │                                            │
│  │  • 10x weight    │                                            │
│  │  • Accumulates   │                                            │
│  └────────┬─────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                            │
│  │    BASELINE      │                                            │
│  │                  │                                            │
│  │  • Fast decay    │                                            │
│  │  • 1x weight     │                                            │
│  │  • Gentle drift  │                                            │
│  └──────────────────┘                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 6: Why This Is Different

### Standard Approach (Wrong)

Most ML systems use symmetric loss:
```
Loss = (prediction - actual)²
```

Undershooting by 10 = Overshooting by 10. Same penalty.

### Survival Approach (Ours)

Asymmetric loss based on outcome:
```
If outcome was bad:
    Loss = 100 × (prediction - actual)²   # 100x penalty for missing danger

If outcome was fine:
    Loss = (prediction - actual)²          # Normal penalty
```

**Why this matters:**

In hiring, if someone:
- Seemed fine, was fine → baseline update (+1)
- Seemed fine, was bad → catastrophic trauma (permanent flag)
- Seemed concerning, was fine → warning decays slowly
- Seemed concerning, was bad → warning reinforced heavily

The system learns like a prey animal, not like a neural network.

---

## Part 7: Practical Implications

### What Changes in the Implementation

**Old approach (symmetric):**
- Treat all observations equally
- Gentle decay on everything
- Average signals over time

**New approach (survival):**
- Classify observations by severity
- Never forget catastrophic events
- Weight negative signals 10x
- Fast-decay positive signals (they're just context)

### Example Scenario

**Situation:** CFO of Company X

**Observations over 8 earnings calls:**
- Calls 1-6: Normal hedging on guidance. Baseline builds.
- Call 7: Unusual hesitation on accounting question. Warning flags.
- Call 8: Company restates earnings, stock drops 30%.

**Symmetric system:** Would average all 8 calls. Call 7 slightly elevated.

**Survival system:**
- Calls 1-6: Baseline = ~0.5 (normal)
- Call 7: Warning = 0.3 (elevated)
- Call 8: **TRAUMA** = max severity, permanent

**Future queries about this CFO:**
- Symmetric: "Slightly elevated historical concern"
- Survival: "**PERMANENT FLAG: Preceded earnings restatement**"

The survival system never forgets the catastrophic event. This is correct behavior.

---

## Part 8: Honest Assessment (Updated)

### What We Actually Have

**A system that:**
1. Records conversations precisely (solved problem)
2. Builds probabilistic expectations (what LLMs already do)
3. Compares observation to expectation (subtraction)
4. **Classifies deltas by severity** (new insight)
5. **Applies asymmetric weighting** (biological learning)
6. **Maintains permanent trauma memory** (survival patterns)
7. Visualizes patterns (standard UI)

### What's Novel

1. **The asymmetric learning model** - Most similar tools use symmetric averaging. We weight negative signals 10x and never forget catastrophic events.

2. **Three-tier memory** - Trauma/Warning/Baseline is not standard in anomaly detection.

3. **Survival framing** - Modeling the system as a prey animal rather than a neutral observer.

### What's Still True (Limitations)

**The base rate problem remains:**
```
If 5% of statements are "interesting"
And your detector is 80% accurate
Then 83% of your alerts are false positives
```

**But the survival model helps because:**
- False positives on danger are CHEAP (extra caution)
- False negatives on danger are EXPENSIVE (missed threat)
- Asymmetric weighting matches this asymmetric cost

### What This Changes About Use Cases

**Stronger for:**
- Pattern detection where some patterns led to known-bad outcomes
- Building "institutional memory" that doesn't forget failures
- Earnings call analysis (outcomes are known, can label catastrophic)

**Still weak for:**
- Real-time "deception detection" (no outcome yet)
- Cases without subsequent validation
- Anything requiring balanced judgment

---

## Part 9: The Path Forward

### Build First (MVP)

1. Audio recording + transcription
2. Basic topic extraction
3. Filler word detection
4. Response latency measurement
5. Simple heat map visualization
6. **Three-tier memory system (trauma/warning/baseline)**

### Build Second (Validation Required)

1. Probabilistic expectation model
2. Surprise calculation
3. **Asymmetric weighting calibration**
4. **Catastrophic event labeling pipeline**

### Critical Path

**The system only works if we can label outcomes.**

- Earnings call → Subsequent stock performance (labellable)
- Interview → Subsequent job performance (labellable with delay)
- Sales call → Deal outcome (labellable)
- Random conversation → ??? (not labellable)

**Without outcome labels, we can't distinguish catastrophic from negative from positive.**

---

## Conclusion: What Do We Actually Have?

**We have a survival-learning system that:**
- Learns like a prey animal, not a neural network
- Never forgets catastrophic events
- Weights negative signals heavily
- Treats positive signals as gentle context

**The biological insight is genuine:**
- Zebras learn in 30 minutes through observational trauma
- Big fish don't bite because they learned from others' deaths
- Asymmetric learning is how real intelligence develops

**The implementation is achievable:**
- Three-tier memory is just three hash tables with different decay rates
- Asymmetric weighting is just different multipliers
- The math is simple; the framing is what matters

**The key requirement is outcome labeling:**
- Without knowing what was "bad," we can't train trauma response
- Earnings calls are ideal (outcome is public, timestamped)
- General "lie detection" remains unsupported

**If we build this honestly, we have something useful:**
- A system that learns from mistakes like survivors do
- An institutional memory that doesn't forget failures
- A tool that flags "this pattern preceded bad outcomes before"

**This is not a lie detector. It's a scar detector.**

It remembers what went wrong, forever.

---

## Appendix: Comparison of Approaches

### Symmetric (Standard ML)

```python
# All signals weighted equally
memory[entity][topic] = 0.95 * old_value + 0.05 * new_signal
```

**Problem:** Forgets catastrophes at same rate as normal events.

### Asymmetric (Survival)

```python
if catastrophic:
    trauma[entity][topic] = max(old, new)  # Permanent
elif negative:
    warning[entity][topic] = 0.99 * old + 0.5 * new  # Heavy, slow-decay
else:
    baseline[entity][topic] = 0.95 * old + 0.05 * new  # Light, fast-decay
```

**Advantage:** Matches biological learning. Never forgets what matters.

### Why This Is Better

| Scenario | Symmetric Result | Survival Result |
|----------|-----------------|-----------------|
| 10 normal calls, 1 disaster | Disaster fades to noise | Disaster permanently flagged |
| Early warning signs followed by bad outcome | Warning decays | Warning reinforced, becomes trauma |
| Consistent good behavior | High baseline | High baseline (same) |
| Near-miss that didn't materialize | Fades quickly | Fades slowly (remains cautionary) |

The survival model retains the information that matters most.

---

*This document reflects the corrected understanding that biological learning is fundamentally asymmetric, and that survival systems must weight negative outcomes far more heavily than positive ones.*
