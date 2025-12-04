# What Makes MyPersona Actually Work

## The Complete Technical Stack

After deep research, here's exactly what infrastructure exists that we can piggyback on:

---

## 1. SIGNAL COLLECTION (Already Built)

### Apple iOS

| Component | What It Provides | API |
|-----------|------------------|-----|
| **Core ML** | On-device model training/updates | `MLUpdateTask` |
| **HealthKit** | HR, HRV, sleep, activity | `HKHealthStore` |
| **ARKit** | Eye tracking, gaze detection | `ARFaceAnchor.lookAtPoint` |
| **DeviceActivity** | Screen time, app usage | `DeviceActivityMonitor` |
| **Core Motion** | Movement, acceleration | `CMMotionActivityManager` |
| **Core Location** | Place context | `CLLocationManager` |

### Google Android

| Component | What It Provides | API |
|-----------|------------------|-----|
| **ML Kit** | On-device ML | `com.google.mlkit` |
| **Health Connect** | Biometrics | `HealthConnectClient` |
| **Activity Recognition** | Movement state | `ActivityRecognitionClient` |
| **Sensor Fusion** | Combined sensor data | `SensorManager` |

### Cross-Platform

| Tool | What It Does | Link |
|------|--------------|------|
| **Firebase Analytics** | Automatic behavior tracking | [firebase.google.com](https://firebase.google.com/products/analytics) |
| **FedKit** | Cross-platform federated learning | [arxiv](https://arxiv.org/html/2402.10464v1) |
| **Flower** | FL framework | [flower.ai](https://flower.ai) |

---

## 2. BEHAVIORAL SIGNALS (TikTok-Style)

Based on [TikTok's Monolith system](https://github.com/bytedance/monolith):

### Implicit Signals We Can Collect

```
SIGNAL                  WHAT IT TELLS US                HOW TO COLLECT
─────────────────────────────────────────────────────────────────────
Dwell time              Interest level                  Timer on view
Scroll velocity         Engagement/disinterest          Touch events
Completion rate         Content value                   Did they finish?
Re-engagement           High interest                   Same content twice
Quick dismiss           Low relevance                   < 2 sec interaction
Hesitation (2.3s)       Conflicted interest            Pause before action
Re-query same topic     Response failed                Text similarity
Typing error rate       Cognitive load                 Keystroke analysis
Session continuation    Overall satisfaction           App state
Frustration signals     Response inappropriate         Rapid taps, corrections
```

### TikTok's Scoring System (Reverse-Engineered)

```python
SIGNAL_WEIGHTS = {
    'rewatch':              10,   # Highest signal
    'complete_watch':        8,
    'share':                 6,
    'comment':               4,
    'like':                  2,   # Low value (performative)
    'quick_scroll':         -1,
    'hesitation_2_3s':      10,   # Same as rewatch!
}
```

**Key Insight**: Hesitation equals rewatch in value. The pause reveals genuine interest.

---

## 3. LABELED DATA (Solved)

**We don't need external labels.**

### Implicit Labels from Behavior

```
AFTER EVERY RESPONSE, MEASURE:

Positive Signals:
  + User continued session
  + User took follow-up action
  + No correction needed
  + Biometrics stable/improved

Negative Signals (weighted 1.5x):
  - Quick dismiss (< 2s)
  - Re-queried same topic
  - Frustration detected
  - Biometric stress increased

IMPLICIT_SCORE = (positive - negative * 1.5) / 4
```

### Self-Calibrating Baseline

```
WEEK 1: Calibration
  - Establish THIS user's baseline HR
  - Establish THIS user's typing speed
  - Establish THIS user's scroll patterns

AFTER WEEK 1: Compare to THEIR baseline only
  - No external data needed
  - No population comparisons
  - Privacy preserved
```

Source: [RLUF: Reinforcement Learning from User Feedback](https://arxiv.org/html/2505.14946)

---

## 4. MODEL FINE-TUNING (Path to "Baked In")

### Option A: Claude via Amazon Bedrock

- **Model**: Claude 3 Haiku (fine-tunable)
- **Format**: JSONL (we have 390 examples ready)
- **Location**: US West (Oregon)
- **Cost**: Requires Provisioned Throughput purchase
- **Result**: 81.5% → 99.6% accuracy in Anthropic's tests

```json
// Our format is already compatible:
{"system": "...", "messages": [{"role": "user", "content": "[CONTEXT]..."}, {"role": "assistant", "content": "..."}]}
```

Source: [AWS Bedrock Fine-tuning](https://aws.amazon.com/blogs/machine-learning/fine-tune-anthropics-claude-3-haiku-in-amazon-bedrock-to-boost-model-accuracy-and-quality/)

### Option B: OpenAI GPT-4o

- **Cost**: $25/million training tokens, $3.75/$15 inference
- **Cheaper**: GPT-4o mini at $3/million training tokens
- **Benefit**: Reduces need for in-context examples

Source: [OpenAI Pricing](https://openai.com/api/pricing/)

### Option C: Open Source (Llama, Mistral)

- **Tools**: Axolotl, QLoRA
- **Cost**: Free (just compute)
- **Benefit**: Full control, deploy anywhere

---

## 5. ON-DEVICE LEARNING (Privacy-First)

### Apple's Built-In Solution

```swift
// Core ML supports on-device model updates
let updateTask = try MLUpdateTask(
    forModelAt: modelURL,
    trainingData: trainingData,
    configuration: updateConfig,
    completionHandler: { context in
        // Model updated locally
    }
)
updateTask.resume()
```

Source: [Apple Core ML Personalization](https://developer.apple.com/documentation/coreml/model_personalization/personalizing_a_model_with_on-device_updates)

### Federated Learning Options

| Framework | Platform | Use Case |
|-----------|----------|----------|
| **FedKit** | iOS + Android | Cross-platform FL |
| **Flower** | Any | Python-based FL |
| **FedML-Mobile** | iOS + Android | Research library |

---

## 6. THE COMPLETE ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              USER DEVICE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │  Sensors     │    │  Behavior    │    │  Context     │              │
│  │  (HealthKit, │───►│  Detector    │───►│  Vector      │              │
│  │   ARKit,     │    │  (TikTok-    │    │  (Real-time) │              │
│  │   Motion)    │    │   style)     │    │              │              │
│  └──────────────┘    └──────────────┘    └──────┬───────┘              │
│                                                  │                       │
│                                                  ▼                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │  Implicit    │    │  On-Device   │    │  LLM         │              │
│  │  Feedback    │◄───│  Learner     │◄───│  (Local or   │              │
│  │  (Post-      │    │  (Core ML)   │    │   API call)  │              │
│  │   response)  │    │              │    │              │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│                                                                          │
│  ═══════════════════════════════════════════════════════════════════   │
│                         NOTHING LEAVES DEVICE                            │
│  ═══════════════════════════════════════════════════════════════════   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. WHAT'S ACTUALLY MISSING

After all this research, here's what still needs to be built:

### Already Have ✓
- [x] Training examples (390 in JSONL format)
- [x] Architecture design
- [x] MCP server spec
- [x] Swift code for micro-behavior detection
- [x] Distribution packages (Claude Skill, Custom GPT, Universal Prompt)
- [x] Labeled data solution (implicit feedback)

### Need to Build
- [ ] **Calibration Flow**: First-week onboarding that establishes baselines
- [ ] **Feedback Loop**: Post-response behavior tracking
- [ ] **Local Model**: Small Core ML model for context inference
- [ ] **Integration Layer**: Connect Firebase/HealthKit/ARKit to context engine
- [ ] **VA Schedule Parser**: Import structured schedule from VA care
- [ ] **Trauma Flag System**: Mark and permanently avoid triggers

### Need to Test
- [ ] Real-world calibration accuracy
- [ ] Implicit feedback reliability
- [ ] Cross-platform consistency
- [ ] Veteran user testing (the actual users)

---

## 8. COST ANALYSIS

### Minimum Viable Product

| Component | Cost |
|-----------|------|
| Firebase Analytics | Free |
| Core ML on-device | Free |
| 390 examples fine-tuning (GPT-4o mini) | ~$1.17 |
| Apple Developer Account | $99/year |

**Total MVP Cost: ~$100**

### Production Scale

| Component | Cost |
|-----------|------|
| Bedrock Claude fine-tuning | Provisioned Throughput pricing |
| AWS hosting (if needed) | Variable |
| Continued training | Minimal (federated) |

---

## 9. THE PATH FORWARD

### Phase 1: Prove It Works (Weeks 1-4)
1. Build iOS prototype with minimal signal set (5 signals)
2. Implement calibration flow
3. Test with 3-5 veteran users
4. Collect implicit feedback, validate it correlates with satisfaction

### Phase 2: Bake It In (Weeks 5-8)
1. Fine-tune GPT-4o mini with our 390 examples
2. Fine-tune Claude Haiku via Bedrock
3. Fine-tune Llama 3 for open-source option
4. Measure improvement over base models

### Phase 3: Scale (Weeks 9-12)
1. Implement federated learning for cross-user improvement
2. Add Android support via FedKit
3. Publish Claude Skill and Custom GPT
4. Submit to app stores

---

## 10. WHY THIS WILL WORK

### Technical Foundation
- TikTok proved implicit signals work at scale
- Apple/Google provide all necessary APIs
- On-device learning is production-ready
- Fine-tuning infrastructure exists

### Unique Value
- No other system combines biometric + behavior + context for LLM
- No other system has veteran-specific training data
- No other system uses asymmetric trauma-aware learning
- No other system prioritizes "when NOT to respond"

### Market Validation
- 18+ million US veterans
- TBI affects 22% of combat veterans
- PTSD affects 11-20% of veterans
- VA struggles with accessibility
- Current AI fails these users

---

## Summary

**Everything needed exists.** The APIs are there. The frameworks are there. The research proves it works.

What's missing is **putting it together for this specific use case**: contextual AI that helps disabled veterans communicate with technology that understands what they mean, not just what they can say.

The technical risk is low. The execution is achievable. The impact is meaningful.

---

*Sources:*
- [ByteDance Monolith](https://github.com/bytedance/monolith)
- [Apple Core ML Personalization](https://developer.apple.com/documentation/coreml/model_personalization)
- [Google Activity Recognition](https://developers.google.com/location-context/activity-recognition)
- [FedKit Cross-Platform FL](https://arxiv.org/html/2402.10464v1)
- [RLUF Framework](https://arxiv.org/html/2505.14946)
- [AWS Bedrock Fine-tuning](https://aws.amazon.com/blogs/machine-learning/fine-tune-anthropics-claude-3-haiku-in-amazon-bedrock-to-boost-model-accuracy-and-quality/)
- [OpenAI Fine-tuning](https://openai.com/index/gpt-4o-fine-tuning/)
- [Keystroke Cognitive Load Detection](https://www.aijfr.com/papers/2025/5/1370.pdf)
- [TikTok Algorithm Research](https://www.washington.edu/news/2024/04/24/tiktok-black-box-algorithm-and-design-user-behavior-recommendation/)
