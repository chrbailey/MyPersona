# MyPersona: Complete Project Plan

## System Breakdown

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MYPERSONA SYSTEM                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   DEPT 1    │  │   DEPT 2    │  │   DEPT 3    │  │   DEPT 4    │        │
│  │   SIGNALS   │  │  INFERENCE  │  │   PROFILE   │  │    MCP      │        │
│  │             │  │   ENGINE    │  │   & MEMORY  │  │   SERVER    │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │               │
│         └────────────────┴────────────────┴────────────────┘               │
│                                   │                                         │
│                          ┌────────▼────────┐                                │
│                          │     DEPT 5      │                                │
│                          │   INTEGRATION   │                                │
│                          │    & TESTING    │                                │
│                          └─────────────────┘                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## DEPARTMENT 1: SIGNALS
**Purpose:** Collect raw data from device sensors

### Module 1.1: Types & Interfaces
```
src/signals/types.ts
```
- SignalBundle interface
- BiometricSignals interface
- LocationSignals interface
- TemporalSignals interface
- SocialSignals interface
- DeviceSignals interface
- PlaceType enum
- MotionType enum

**Deliverable:** Complete TypeScript type definitions

---

### Module 1.2: Signal Bus
```
src/signals/bus.ts
```
- Event emitter for signal updates
- Signal aggregation
- Rate limiting
- Signal freshness tracking

**Deliverable:** Working signal bus that aggregates multiple sources

---

### Module 1.3: Mock Signals (For Testing)
```
src/signals/mock/
├── generator.ts          # Generate realistic mock signals
├── scenarios.ts          # Pre-defined test scenarios
└── playback.ts           # Playback recorded signal sequences
```

**Scenarios to implement:**
1. Saturday night at club (romantic context)
2. Workday morning meeting (stress context)
3. Quiet night looking at moon (reflective context)
4. Family Christmas morning (parental context)
5. Gym workout (physical context)
6. Late night unfamiliar location (safety context)

**Deliverable:** Mock signal generator with 6+ scenarios

---

### Module 1.4: Desktop Signals (Limited)
```
src/signals/platforms/desktop.ts
```
- Time/date
- Calendar (if available)
- Screen state
- Active app (if available)
- No biometrics (desktop limitation)

**Deliverable:** Desktop signal collector

---

### Module 1.5: iOS Signals (Future)
```
src/signals/platforms/ios.ts
```
- HealthKit integration
- CoreLocation
- Calendar/EventKit
- Contacts proximity
- Screen/motion state

**Deliverable:** iOS signal collector (spec only for now)

---

### Module 1.6: Android Signals (Future)
```
src/signals/platforms/android.ts
```
- Health Connect
- Location services
- Calendar
- Nearby devices

**Deliverable:** Android signal collector (spec only for now)

---

## DEPARTMENT 2: INFERENCE ENGINE
**Purpose:** Transform raw signals into contextual understanding (THE IP)

### Module 2.1: State Inference
```
src/inference/state.ts
```
- Physical state detection (resting/active/exercising/sleeping)
- Emotional state inference (calm/stressed/excited/anxious)
- Social state detection (alone/with_known/with_unknown/in_crowd)
- Cognitive state inference (focused/relaxed/distracted/reflective)

**Deliverable:** State inference from signals

---

### Module 2.2: Signal Disambiguation
```
src/inference/disambiguate.ts
```
Core logic: Same signal means different things in different contexts

**Rules to implement:**
```
HR elevated + stairs → exercise
HR elevated + social venue + weekend → excitement
HR elevated + work + meeting → stress
HR elevated + alone + still → anxiety
HR elevated + known person + home → intimate
```

**Deliverable:** Disambiguation engine with 10+ rules

---

### Module 2.3: Biological Model
```
src/inference/biological.ts
```
- Age → Life Stage mapping
- Life Stage → Dominant Drives
- Drive-based interpretation bias

**Life Stages:**
- child (<13)
- adolescent (13-17)
- young_adult (18-25)
- adult (26-40)
- middle_adult (41-60)
- older_adult (61-80)
- elder (81+)

**Drives:**
- play, identity, status, mate_acquisition
- mate_retention, parental_care, career
- legacy, comfort, safety, meaning, transcendence

**Deliverable:** Complete biological model

---

### Module 2.4: Needs Model (Maslow)
```
src/inference/needs.ts
```
- Real-time need level detection
- Physiological overrides
- Safety detection
- Belonging/Esteem/Actualization/Transcendence detection

**Deliverable:** Maslow-based needs detector

---

### Module 2.5: Quiet Mode Detection
```
src/inference/quiet.ts
```
**Conditions for quiet mode:**
- Alone + reflective + stationary + screen off
- Late night + calm + not using device
- Recording voice note + alone
- Sleeping or about to sleep
- Major life event contemplation

**Deliverable:** Quiet mode detector

---

### Module 2.6: Intent Interpretation
```
src/inference/intent.ts
```
- Combine all layers (state, bio, needs)
- Generate natural language interpretation
- Confidence scoring

**Deliverable:** Intent interpreter

---

### Module 2.7: Context Pipeline
```
src/inference/context.ts
```
- Orchestrate all inference modules
- Generate complete Context object
- Handle transitions between states

**Deliverable:** Main inference pipeline

---

## DEPARTMENT 3: PROFILE & MEMORY
**Purpose:** Learn patterns and remember outcomes

### Module 3.1: User Profile
```
src/profile/user.ts
```
- Birth year / age calculation
- Life stage determination
- Baseline biometrics (learned)
- Work schedule patterns
- Sleep patterns
- Exercise patterns

**Deliverable:** User profile structure and persistence

---

### Module 3.2: Pattern Learning
```
src/profile/patterns.ts
```
- Learn typical wake/sleep times
- Learn work days
- Learn exercise patterns
- Learn social patterns
- Exponential moving average for baselines

**Deliverable:** Pattern learning engine

---

### Module 3.3: Survival Memory
```
src/profile/memory.ts
```
**Three-tier memory:**
- Trauma (permanent, never decays)
- Warnings (heavy weight, slow decay)
- Baseline (light weight, fast decay)

**Operations:**
- absorb(entity, topic, delta)
- getImpression(entity, topic)
- applyTimeDecay()

**Deliverable:** Asymmetric survival memory system

---

### Module 3.4: Profile Persistence
```
src/profile/store.ts
```
- Save profile to disk
- Load profile on startup
- Migration between versions
- Privacy-safe export

**Deliverable:** Profile storage system

---

## DEPARTMENT 4: MCP SERVER
**Purpose:** Expose MyPersona to any LLM client

### Module 4.1: Server Core
```
src/server/index.ts
```
- MCP server initialization
- Capability declaration
- Transport setup (stdio/HTTP)

**Deliverable:** Basic MCP server running

---

### Module 4.2: Resources
```
src/server/resources.ts
```
**Resources:**
- `persona://context` - Current context as text
- `persona://quiet` - Quiet mode status
- `persona://profile` - User profile summary

**Deliverable:** MCP resources implementation

---

### Module 4.3: Tools
```
src/server/tools.ts
```
**Tools:**
- `enrich_query(query)` → enriched query with context
- `check_quiet_mode()` → boolean
- `check_response_appropriate(response)` → validation
- `get_response_style()` → style guidance

**Deliverable:** MCP tools implementation

---

### Module 4.4: Text Output
```
src/output/text.ts
```
- Context → natural language
- State description
- Drive description
- Need level description
- Response style guidance

**Deliverable:** Natural language output generator

---

### Module 4.5: Response Validation
```
src/output/validate.ts
```
- Check if proposed response matches context
- Verbosity appropriateness
- Tone appropriateness
- Quiet mode compliance

**Deliverable:** Response validator

---

## DEPARTMENT 5: INTEGRATION & TESTING
**Purpose:** Ensure everything works together

### Module 5.1: Scenario Tests
```
test/scenarios/
├── saturday-night.test.ts
├── work-meeting.test.ts
├── quiet-moon.test.ts
├── family-morning.test.ts
├── gym-workout.test.ts
└── unfamiliar-late.test.ts
```

**Each test:**
1. Load mock signals for scenario
2. Run through inference pipeline
3. Verify context output matches expectation
4. Verify LLM guidance is appropriate

**Deliverable:** 6+ scenario tests passing

---

### Module 5.2: Disambiguation Tests
```
test/disambiguation.test.ts
```
- Test each disambiguation rule
- Verify correct state inference
- Edge case handling

**Deliverable:** Disambiguation test suite

---

### Module 5.3: Memory Tests
```
test/memory.test.ts
```
- Trauma never decays
- Warnings decay slowly
- Baseline decays fast
- Absorption works correctly

**Deliverable:** Memory system tests

---

### Module 5.4: Integration Tests
```
test/integration/
├── full-pipeline.test.ts
├── mcp-server.test.ts
└── claude-desktop.test.ts
```

**Deliverable:** End-to-end integration tests

---

### Module 5.5: Performance Tests
```
test/performance/
├── inference-speed.test.ts
└── memory-usage.test.ts
```
- Context inference < 50ms
- Memory footprint reasonable

**Deliverable:** Performance benchmarks

---

## EXECUTION ORDER

### Phase 1: Foundation (Modules I Can Build Now)
```
Week 1:
├── 1.1 Types & Interfaces ✓
├── 1.2 Signal Bus ✓
├── 1.3 Mock Signals ✓
└── 4.1 Server Core ✓

Week 2:
├── 2.1 State Inference ✓
├── 2.2 Disambiguation ✓
├── 2.3 Biological Model ✓
└── 2.4 Needs Model ✓
```

### Phase 2: Core Intelligence
```
Week 3:
├── 2.5 Quiet Mode ✓
├── 2.6 Intent Interpretation ✓
├── 2.7 Context Pipeline ✓
└── 4.4 Text Output ✓

Week 4:
├── 4.2 Resources ✓
├── 4.3 Tools ✓
├── 4.5 Response Validation ✓
└── 1.4 Desktop Signals ✓
```

### Phase 3: Memory & Learning
```
Week 5:
├── 3.1 User Profile ✓
├── 3.2 Pattern Learning ✓
├── 3.3 Survival Memory ✓
└── 3.4 Profile Persistence ✓
```

### Phase 4: Testing & Polish
```
Week 6:
├── 5.1 Scenario Tests ✓
├── 5.2 Disambiguation Tests ✓
├── 5.3 Memory Tests ✓
└── 5.4 Integration Tests ✓

Week 7:
├── 5.5 Performance Tests ✓
├── Documentation ✓
├── Claude Desktop Integration ✓
└── Demo Scenarios ✓
```

### Phase 5: Platform Expansion (Future)
```
Week 8+:
├── 1.5 iOS Signals (requires native dev)
├── 1.6 Android Signals (requires native dev)
└── Mobile MCP Client
```

---

## FILE STRUCTURE

```
mypersona/
├── src/
│   ├── index.ts                    # Entry point
│   │
│   ├── signals/
│   │   ├── types.ts                # All signal types
│   │   ├── bus.ts                  # Signal aggregation
│   │   ├── mock/
│   │   │   ├── generator.ts
│   │   │   ├── scenarios.ts
│   │   │   └── playback.ts
│   │   └── platforms/
│   │       ├── desktop.ts
│   │       ├── ios.ts              # Spec only
│   │       └── android.ts          # Spec only
│   │
│   ├── inference/
│   │   ├── state.ts                # State detection
│   │   ├── disambiguate.ts         # Signal disambiguation
│   │   ├── biological.ts           # Age → drives
│   │   ├── needs.ts                # Maslow detection
│   │   ├── quiet.ts                # Quiet mode
│   │   ├── intent.ts               # Intent interpretation
│   │   └── context.ts              # Main pipeline
│   │
│   ├── profile/
│   │   ├── user.ts                 # User profile
│   │   ├── patterns.ts             # Pattern learning
│   │   ├── memory.ts               # Survival memory
│   │   └── store.ts                # Persistence
│   │
│   ├── server/
│   │   ├── index.ts                # MCP server
│   │   ├── resources.ts            # MCP resources
│   │   └── tools.ts                # MCP tools
│   │
│   └── output/
│       ├── text.ts                 # Context → text
│       └── validate.ts             # Response validation
│
├── test/
│   ├── scenarios/
│   │   ├── saturday-night.test.ts
│   │   ├── work-meeting.test.ts
│   │   ├── quiet-moon.test.ts
│   │   ├── family-morning.test.ts
│   │   ├── gym-workout.test.ts
│   │   └── unfamiliar-late.test.ts
│   │
│   ├── disambiguation.test.ts
│   ├── memory.test.ts
│   │
│   ├── integration/
│   │   ├── full-pipeline.test.ts
│   │   ├── mcp-server.test.ts
│   │   └── claude-desktop.test.ts
│   │
│   └── performance/
│       ├── inference-speed.test.ts
│       └── memory-usage.test.ts
│
├── docs/
│   ├── architecture.md
│   ├── mypersona_architecture.md
│   ├── mcp_server_spec.md
│   ├── three_model_architecture.md
│   └── critical_review.md
│
├── config/
│   └── claude_desktop_config.json
│
├── package.json
├── tsconfig.json
├── PROJECT_PLAN.md                 # This file
└── README.md
```

---

## DELIVERABLES BY MODULE

| Module | Files | Lines (Est) | Complexity |
|--------|-------|-------------|------------|
| 1.1 Types | 1 | 200 | Low |
| 1.2 Signal Bus | 1 | 150 | Medium |
| 1.3 Mock Signals | 3 | 400 | Medium |
| 1.4 Desktop Signals | 1 | 100 | Low |
| 2.1 State Inference | 1 | 150 | Medium |
| 2.2 Disambiguation | 1 | 250 | High |
| 2.3 Biological Model | 1 | 150 | Medium |
| 2.4 Needs Model | 1 | 200 | Medium |
| 2.5 Quiet Mode | 1 | 100 | Medium |
| 2.6 Intent | 1 | 150 | Medium |
| 2.7 Context Pipeline | 1 | 200 | High |
| 3.1 User Profile | 1 | 150 | Medium |
| 3.2 Pattern Learning | 1 | 200 | High |
| 3.3 Survival Memory | 1 | 250 | High |
| 3.4 Profile Store | 1 | 150 | Medium |
| 4.1 Server Core | 1 | 100 | Medium |
| 4.2 Resources | 1 | 150 | Medium |
| 4.3 Tools | 1 | 200 | Medium |
| 4.4 Text Output | 1 | 200 | Medium |
| 4.5 Validation | 1 | 150 | Medium |
| 5.x Tests | 10 | 800 | Medium |
| **TOTAL** | **31** | **~4,200** | - |

---

## READY TO BUILD

I can start building this now. The order is:

1. **Start with types** (foundation everything else depends on)
2. **Build mock signals** (so we can test without real sensors)
3. **Build inference engine** (the core IP)
4. **Wire up MCP server** (the interface)
5. **Add memory/learning** (the persistence layer)
6. **Test everything** (prove it works)

**Command to begin:**
```
Tell me to start building, and I'll begin with Department 1, Module 1.1 (Types & Interfaces)
```

---

## DEPARTMENT 6: DISTRIBUTION
**Purpose:** Get MyPersona concept into every model ecosystem

### Module 6.1: Claude Skill
```
skills/claude/
├── mypersona.md              # Skill definition
├── examples.md               # Example interactions
└── instructions.md           # How to use
```

**The skill teaches Claude to:**
- Ask for context signals (age, location, time, situation)
- Infer real intent from stated query
- Adjust response based on life stage/drives
- Know when to be quiet

**Deliverable:** Publishable Claude Skill

---

### Module 6.2: Custom GPT
```
skills/openai/
├── instructions.md           # GPT instructions
├── conversation_starters.md  # Example prompts
└── knowledge.md              # Uploaded context
```

**The GPT is configured to:**
- Understand the MyPersona framework
- Ask clarifying context questions
- Interpret queries through biological/situational lens
- Provide context-aware responses

**Deliverable:** Publishable Custom GPT

---

### Module 6.3: Training Examples (250+)
```
examples/
├── by_scenario/
│   ├── romantic_context.json       # 30 examples
│   ├── work_stress.json            # 30 examples
│   ├── parental.json               # 30 examples
│   ├── health_safety.json          # 30 examples
│   ├── reflective_quiet.json       # 30 examples
│   ├── social_status.json          # 30 examples
│   ├── comfort_elderly.json        # 30 examples
│   └── play_children.json          # 30 examples
│
├── by_age/
│   ├── age_11.json                 # 20 examples
│   ├── age_21.json                 # 20 examples
│   ├── age_31.json                 # 20 examples
│   ├── age_41.json                 # 20 examples
│   ├── age_61.json                 # 20 examples
│   └── age_81.json                 # 20 examples
│
└── format.md                       # Example format spec
```

**Example format:**
```json
{
  "id": "romantic_001",
  "signals": {
    "age": 24,
    "time": "Saturday 11:45pm",
    "location": "social venue",
    "heart_rate": 98,
    "social": "1 unknown person nearby, close proximity",
    "motion": "minimal"
  },
  "query": "What's the weather?",
  "wrong_response": "The current temperature is 65°F with clear skies.",
  "right_response": "Nice night - 65°, clear. The waterfront's about 10 minutes away.",
  "reasoning": "User in romantic context, considering leaving venue with companion. Weather query is about ambiance and walkability, not meteorology."
}
```

**Deliverable:** 250+ training examples across all scenarios and ages

---

### Module 6.4: Universal Prompt
```
prompts/
├── system_prompt.md          # Universal system prompt
├── context_template.md       # How to describe context
└── response_guidelines.md    # How to respond
```

**This prompt works with ANY model:**
```
You are an AI that understands what users REALLY mean, not just what they say.

Before responding to any query, consider:
1. USER CONTEXT: What signals do you have about their situation?
2. BIOLOGICAL DRIVES: Based on their age/life stage, what motivates them?
3. NEED LEVEL: What level of Maslow's hierarchy is active right now?
4. QUIET MODE: Should you even respond, or just witness?

Then interpret the query through this lens and respond appropriately.

[Examples follow...]
```

**Deliverable:** Drop-in system prompt for any LLM

---

### Module 6.5: Documentation for Developers
```
docs/
├── integration_guide.md      # How to integrate MyPersona
├── signal_reference.md       # All signal types
├── inference_reference.md    # How inference works
└── api_reference.md          # API documentation
```

**Deliverable:** Complete developer documentation

---

## DISTRIBUTION EXECUTION

### Week 1: Examples
- Create example format specification
- Generate 30 romantic context examples
- Generate 30 work stress examples
- Generate 30 parental examples

### Week 2: More Examples
- Generate remaining scenario examples (5 categories × 30 = 150)
- Generate age-based examples (6 ages × 20 = 120)
- Review and refine all examples

### Week 3: Skills/GPTs
- Create Claude Skill definition
- Create Custom GPT configuration
- Create universal system prompt
- Test with real queries

### Week 4: Documentation & Launch
- Complete integration guide
- Create demo videos
- Publish Claude Skill
- Publish Custom GPT
- Open source examples

---

## WHY THIS MATTERS

**MCP Server alone:** Only works with MCP-compatible clients

**Skills + GPTs + Examples:**
- Works with Claude (Skill)
- Works with ChatGPT (Custom GPT)
- Works with Llama, Gemini, Mistral (via examples/prompt)
- Trains the concept into the ecosystem
- Others can build on it
- Network effect

**The 250 examples are the real distribution mechanism.**

Every developer who sees them understands the concept.
Every model fine-tuned on them learns the pattern.
Every AI assistant built with them inherits the insight.

---

## SUCCESS CRITERIA

When complete, this test passes:

**Input:**
```
Signals: Saturday 11:45pm, social venue, HR 98,
         1 unknown person nearby (close), movement minimal
Profile: Age 24
```

**Output:**
```
User state: active, with new people, excited
Life stage context: mate_acquisition orientation
Current priority: esteem-level needs
Likely intent: Considering leaving venue with someone,
               wants to know if outdoor walk is viable
Suggested approach: casual, concise
```

**LLM with this context responds to "What's the weather?" with:**
```
"Nice night - 65°, clear. The waterfront's about 10 minutes away."
```

**Not:**
```
"The current temperature is 65°F with clear skies and
a humidity of 45%. The UV index is 0."
```

---

*This plan enables systematic implementation of the entire MyPersona system.*
