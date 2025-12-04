# MyPersona: Real-Time Adaptive Learning

## The TikTok Insight

TikTok proved that **micro-behaviors are more honest than explicit signals**:

| Signal | TikTok Points | Why It Matters |
|--------|---------------|----------------|
| Rewatch/Loop | 10 | Unconscious repeat = genuine interest |
| Complete watch | 8 | Stayed till the end |
| Share to others | 6 | Worth sharing = high value |
| Comment/Reply | 4 | Engaged enough to type |
| Basic like | 2 | Low effort, often performative |
| Quick scroll | -1 | **Negative signal** |
| **2.3 second hesitation** | >like | Pause before scrolling = conflicted interest |

**Key insight**: TikTok values hesitations over likes. The pause reveals what the conscious mind won't admit.

## What We Can Piggyback On

### 1. Apple Core ML (On-Device Learning)
- **Available since Core ML 3**: On-device training while app runs
- **iOS 18**: 3B parameter on-device model, ~33 tokens/s on M1
- **Privacy**: All processing local, HIPAA/GDPR compliant by default
- **How to use**: Convert model with `respect_trainable` flag, updates happen locally

```swift
// Core ML supports on-device model updates
let modelConfig = MLModelConfiguration()
modelConfig.computeUnits = .all // CPU, GPU, Neural Engine
```

### 2. ARKit Eye Tracking
- **lookAtPoint**: 3D coordinates of where user is looking
- **leftEyeTransform / rightEyeTransform**: Precise gaze vectors
- **iOS 18 Accessibility**: Built-in eye tracking for navigation
- **Limitation**: Requires face visibility (front camera)

```swift
// ARKit gaze tracking
if let faceAnchor = anchor as? ARFaceAnchor {
    let gazePoint = faceAnchor.lookAtPoint
    let dwellTime = calculateDwellTime(at: gazePoint)
    // Hesitation > 2.3 seconds = high interest signal
}
```

### 3. Screen Time / DeviceActivity Framework
- **DeviceActivity**: Monitor app usage patterns
- **Opaque tokens**: Privacy-preserving (no actual identifiers)
- **Triggers**: Fire events based on usage patterns
- **Sandboxed**: Data stays on device

### 4. Federated Learning Pattern
- **Used by**: Google Gboard, Apple Siri
- **How it works**: Learn locally, share only model updates (not data)
- **Perfect for veterans**: Ultra-private, data never leaves device

## Real-Time Signal Fusion Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SENSOR LAYER (Raw Signals)                    │
├─────────────────────────────────────────────────────────────────┤
│ HealthKit      │ ARKit        │ DeviceActivity │ Motion/Location│
│ - Heart rate   │ - Gaze point │ - App dwell    │ - Movement     │
│ - HRV          │ - Blink rate │ - Switch freq  │ - Location     │
│ - Sleep stage  │ - Pupil size │ - Scroll speed │ - Elevation    │
│ - Blood O2     │ - Look away  │ - Pause time   │ - Speed        │
└────────┬───────┴──────┬───────┴───────┬────────┴───────┬────────┘
         │              │               │                │
         ▼              ▼               ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  MICRO-BEHAVIOR DETECTOR                         │
├─────────────────────────────────────────────────────────────────┤
│ Hesitation Detection:                                            │
│   if (gaze_dwell > 2.3s) interest_signal += 10                  │
│   if (scroll_pause > 1.5s) considering = true                   │
│   if (reread_same_content) comprehension_check = true           │
│                                                                  │
│ Negative Signals:                                                │
│   if (quick_scroll < 0.5s) disinterest = true                   │
│   if (app_switch_rapid) overwhelm_likely = true                 │
│   if (repeated_back_button) frustration_detected = true         │
│                                                                  │
│ Stress Indicators:                                               │
│   if (hr_spike + no_movement) anxiety_signal = true             │
│   if (typing_speed_drops) fatigue_or_struggle = true            │
│   if (error_correction_rate_up) cognitive_load_high = true      │
└────────────────────────────────────────────────────────────────┬┘
                                                                  │
                                                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│              ASYMMETRIC LEARNING ENGINE (On-Device)              │
├─────────────────────────────────────────────────────────────────┤
│ Learning Rate by Signal Type:                                    │
│                                                                  │
│ TRAUMA/CRISIS (α = 1.0, no decay):                              │
│   - Panic attack detected                                        │
│   - PTSD trigger identified                                      │
│   - Suicidal ideation signals                                   │
│   → PERMANENT memory, never suggest similar context again        │
│                                                                  │
│ WARNING (α = 0.3, slow decay τ = 30 days):                      │
│   - Anxiety spike in specific context                           │
│   - Frustration at specific UI pattern                          │
│   - Overwhelm at certain times of day                           │
│   → Persistent but can fade if counter-evidence appears         │
│                                                                  │
│ BASELINE (α = 0.1, fast decay τ = 7 days):                      │
│   - Preference for brief responses                              │
│   - Morning vs evening patterns                                  │
│   - Content type interests                                      │
│   → Adaptive, changes with recent behavior                       │
└────────────────────────────────────────────────────────────────┬┘
                                                                  │
                                                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CONTEXT VECTOR (Real-Time)                    │
├─────────────────────────────────────────────────────────────────┤
│ {                                                                │
│   "current_state": {                                             │
│     "stress_level": 0.72,        // from biometrics + behavior  │
│     "attention_quality": 0.45,   // from gaze + dwell time      │
│     "cognitive_load": 0.81,      // from error rate + speed     │
│     "social_context": "alone",   // from calendar + location    │
│     "time_pressure": 0.30        // from calendar analysis      │
│   },                                                             │
│   "learned_patterns": {                                          │
│     "prefers_brief": 0.85,       // learned from scroll behavior│
│     "morning_anxiety": 0.67,     // learned from biometric+time │
│     "va_appointment_stress": 0.92, // learned from calendar+hr  │
│     "typing_difficulty": 0.78    // learned from error patterns │
│   },                                                             │
│   "avoid_triggers": [            // trauma-tier, permanent      │
│     "crowded_space_suggestions",                                 │
│     "time_pressure_language"                                     │
│   ]                                                              │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
```

## The "TikTok for Understanding" Algorithm

### Continuous Scoring System

```python
class RealTimeContextScorer:
    def __init__(self):
        self.trauma_memories = {}      # Never decay
        self.warning_signals = {}      # Slow decay (τ=30d)
        self.baseline_patterns = {}    # Fast decay (τ=7d)

    def process_micro_behavior(self, signal):
        """Process every micro-behavior in real-time"""

        # HESITATION DETECTION (TikTok's secret sauce)
        if signal.type == "gaze_dwell":
            if signal.duration > 2.3:  # seconds
                self.boost_interest(signal.content, weight=10)
            elif signal.duration < 0.5:
                self.reduce_interest(signal.content, weight=-1)

        # FRUSTRATION DETECTION
        if signal.type == "repeated_tap":
            self.flag_ui_frustration(signal.element)
            self.increase_assistance_level()

        # COGNITIVE LOAD DETECTION
        if signal.type == "typing":
            error_rate = signal.corrections / signal.keystrokes
            if error_rate > 0.3:  # 30% error rate
                self.flag_cognitive_load()
                self.simplify_next_response()

        # OVERWHELM DETECTION
        if signal.type == "app_switch":
            if self.recent_switches > 5 in last_minute:
                self.flag_overwhelm()
                self.reduce_information_density()

    def update_asymmetric(self, category, signal, value):
        """Apply asymmetric learning rates"""

        if category == "trauma":
            # PERMANENT - no decay, instant full learning
            self.trauma_memories[signal] = value

        elif category == "warning":
            # SLOW DECAY - weighted toward negative signals
            alpha = 0.3 if value < 0 else 0.1  # 3x learning for negative
            current = self.warning_signals.get(signal, 0)
            self.warning_signals[signal] = (1 - alpha) * current + alpha * value

        elif category == "baseline":
            # FAST DECAY - normal EMA
            alpha = 0.1
            current = self.baseline_patterns.get(signal, 0)
            self.baseline_patterns[signal] = (1 - alpha) * current + alpha * value
```

### What Changes in Milliseconds

```
                    The Girl Walks In The Room
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ BEFORE (alone, elevated HR, looking at work email)              │
│ Context: work_stress, deadline_pressure, cognitive_focus        │
│ Response style: brief, practical, task-focused                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                      [Social proximity detected]
                      [HR pattern changed]
                      [Gaze shifted from screen]
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ AFTER (someone nearby, HR pattern different, attention split)  │
│ Context: social_awareness, divided_attention, status_conscious │
│ Response style: shorter, discreet, context-aware               │
└─────────────────────────────────────────────────────────────────┘
                              │
                        < 200ms transition
```

## Implementation: Piggybacking on iOS

### Required Frameworks

```swift
import CoreML          // On-device learning
import ARKit           // Gaze tracking
import HealthKit       // Biometrics
import DeviceActivity  // Usage patterns
import CoreMotion      // Movement
import CoreLocation    // Place context
```

### Privacy-First Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         ON-DEVICE ONLY                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Raw Sensors ──► Feature Extraction ──► Context Vector ──► LLM  │
│       │                  │                    │                 │
│       │                  │                    │                 │
│       ▼                  ▼                    ▼                 │
│  [DELETED]          [DELETED]           [Encrypted]             │
│  immediately        after processing    local storage           │
│                                                                  │
│  Nothing leaves the device. Ever.                               │
│  Not even "anonymized" data.                                    │
│  Veterans' privacy is non-negotiable.                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### VA Schedule Integration

```swift
// Veterans often have structured days from VA care
// The system learns and respects this structure

struct VAScheduleAwareness {
    // Prescribed quiet times
    var sleepWindow: DateInterval  // e.g., 10pm - 6am
    var restPeriods: [DateInterval] // Afternoon rest

    // Known high-stress times
    var appointmentBuffer: TimeInterval = 3600 // 1 hour before/after

    func shouldReduceNotifications(at time: Date) -> Bool {
        // During prescribed rest: minimal interruption
        // Before VA appointments: extra calm
        // After difficult appointments: recovery mode
    }

    func adjustResponseStyle(for context: VAContext) -> ResponseStyle {
        switch context {
        case .preAppointment:
            return .calm, .supportive, .brief
        case .postAppointment:
            return .gentle, .no_demands, .available
        case .prescribedRest:
            return .minimal, .only_urgent
        case .structuredActivity:
            return .supportive, .task_focused
        }
    }
}
```

## What TikTok Does That We Borrow

| TikTok Pattern | MyPersona Application |
|----------------|----------------------|
| Watch time > completion | Response read time > acknowledged |
| 2.3s hesitation = interest | Pause before input = processing |
| Quick scroll = disinterest | Quick dismiss = response too long |
| Rewatch = high value | Re-read = confusion or importance |
| A/B test on 300 users | Self-compare morning vs evening |
| Negative signals weighted | Frustration signals weighted 10x |

## What We Do That TikTok Doesn't

| MyPersona Unique | Why It Matters for Veterans |
|------------------|----------------------------|
| Trauma-tier never decays | PTSD triggers stay avoided forever |
| VA schedule awareness | Respect prescribed structure |
| Cognitive load detection | Adapt when TBI makes things hard |
| Physical limitation awareness | Know when fingers don't work |
| Federated learning only | Data never leaves, period |
| Quiet mode by default | Sometimes silence is the response |

## Measurement: How We Know It's Working

```python
# Success metrics for adaptive learning

class AdaptiveSuccessMetrics:
    # Reduction in frustration signals over time
    frustration_frequency: float  # Should decrease

    # Response appropriateness (did they engage or dismiss?)
    response_acceptance_rate: float  # Should increase

    # Cognitive load accommodation
    retry_rate: float  # Should decrease (got it right first time)

    # Quiet mode accuracy
    false_interruption_rate: float  # Should approach zero

    # Crisis prevention (most important)
    early_intervention_success: float  # Caught before escalation
```

## Sources and Prior Art

Research and platforms this builds on:
- [TikTok Algorithm Research (UW)](https://www.washington.edu/news/2024/04/24/tiktok-black-box-algorithm-and-design-user-behavior-recommendation/)
- [Apple Core ML On-Device Learning](https://developer.apple.com/machine-learning/core-ml/)
- [iOS 18 Eye Tracking Accessibility](https://9to5mac.com/2024/05/15/apple-previews-ios-18-accessibility-features-including-eye-tracking/)
- [Apple Screen Time API](https://developer.apple.com/documentation/screentime)
- [Federated Learning for Mobile Apps](https://research.aimultiple.com/federated-learning/)
- [Privacy-Preserving Mobile Health](https://www.sciencedirect.com/science/article/pii/S0167739X24003972)

---

*"The best technology is invisible. For a veteran with TBI, the system should understand without being told. For one with missing digits, it should anticipate without extra taps. The learning happens silently, privately, continuously - always in service of reducing the gap between what they mean and what they can express."*
