# MyPersona: Discourse Delta Detection System

## Executive Summary

A real-time event detection system that identifies market-moving events by analyzing the **gap between what IS being said and what SHOULD be said** on social platforms (starting with X/Twitter). Markets provide immediate validation - if our detected "discourse deltas" correlate with price movements, the model works.

## Core Thesis

> **When people collectively avoid discussing something they normally would, or when expected discourse patterns break, something significant is happening.**

This is detectable before traditional signals because:
1. Insiders change their communication patterns before events
2. Coordinated silence is as informative as coordinated messaging
3. Topic avoidance creates measurable gaps in discourse networks

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DISCOURSE DELTA ENGINE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │   X/Twitter  │    │  Expectation │    │    Delta     │    │  Market   │ │
│  │   Ingestion  │───▶│    Model     │───▶│  Detection   │───▶│ Validator │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│         │                   │                   │                   │       │
│         ▼                   ▼                   ▼                   ▼       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         EVENT STORE                                   │  │
│  │  (Discourse Snapshots, Expected Patterns, Deltas, Market Outcomes)   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│                          ┌──────────────────┐                               │
│                          │  Feedback Loop   │                               │
│                          │  (Model Tuning)  │                               │
│                          └──────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## The Four Pillars

### 1. What IS Being Said (Observed Discourse)
- Real-time ingestion of X posts, replies, quote tweets
- Entity extraction (companies, people, topics, tickers)
- Sentiment and tone classification
- Relationship mapping (who talks to whom about what)

### 2. What SHOULD Be Said (Expected Discourse)
- Historical baseline per entity/topic/time-window
- Contextual triggers (earnings, product launches, news)
- Network expectations (if A talks about X, B usually responds)
- Seasonal/cyclical patterns

### 3. The Delta (Discourse Gap)
- Missing expected topics
- Unusual silence from typically active voices
- Broken conversation chains
- Tone shifts without topic shifts
- New entrants to conversations (who shouldn't be there)
- Absent participants (who should be there)

### 4. Market Validation
- Correlate deltas with price movements
- Track prediction accuracy over time
- Build confidence scores per delta type
- Immediate feedback loop

## Data Flow Detail

```
[X API Stream]
      │
      ▼
┌─────────────────┐
│ Raw Post Queue  │ ← Firehose of posts matching tracked entities
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Preprocessing   │
│ - Dedup         │
│ - Language Det  │
│ - Bot Filter    │
│ - Entity Extract│
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Current State   │     │ Expected State  │
│ Builder         │     │ Generator       │
│                 │     │                 │
│ "What IS"       │     │ "What SHOULD"   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
            ┌─────────────────┐
            │ Delta Detector  │
            │                 │
            │ - Missing Topics│
            │ - Silent Voices │
            │ - Tone Shifts   │
            │ - Pattern Breaks│
            └────────┬────────┘
                     │
                     ▼
            ┌─────────────────┐
            │ Event Classifier│
            │                 │
            │ Confidence Score│
            │ Event Type      │
            │ Affected Entity │
            └────────┬────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│ Alert System    │     │ Market Tracker  │
│                 │     │                 │
│ Real-time       │     │ Price at T+0    │
│ Notifications   │     │ Price at T+1h   │
│                 │     │ Price at T+24h  │
└─────────────────┘     └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Validation      │
                       │ Feedback Loop   │
                       │                 │
                       │ Did delta       │
                       │ predict move?   │
                       └─────────────────┘
```

## Key Innovation: The Expectation Model

Most sentiment analysis asks "what are people saying?"

We ask: **"What SHOULD people be saying right now that they're NOT?"**

### Building Expectations

```python
# Conceptual expectation model
class DiscourseExpectation:
    entity: str              # e.g., "$TSLA", "@elonmusk", "Tesla"
    time_window: TimeWindow  # e.g., "market hours", "post-earnings"

    expected_topics: List[Topic]           # Topics usually discussed
    expected_voices: List[Account]          # Who usually speaks
    expected_sentiment_range: (float, float) # Normal sentiment bounds
    expected_volume_range: (int, int)        # Normal post volume
    expected_response_patterns: List[Pattern] # Who responds to whom

    # Contextual modifiers
    triggers: List[Trigger]  # Events that change expectations
    # e.g., "If earnings released, expect 10x volume, CFO commentary"
```

### Delta Types We Detect

| Delta Type | Description | Example |
|------------|-------------|---------|
| **Topic Absence** | Expected topic not mentioned | Company stops mentioning key product |
| **Voice Silence** | Usually active account goes quiet | CEO silent during crisis |
| **Volume Collapse** | Sudden drop in discussion | Coordinated non-discussion |
| **Sentiment Decoupling** | Tone doesn't match news | Positive news, negative undertone |
| **Network Break** | Expected responders don't respond | Usual defenders absent |
| **New Voice Intrusion** | Unexpected accounts suddenly active | Lawyers start posting |
| **Topic Substitution** | Discussing B instead of A | Avoiding real issue |
| **Temporal Shift** | Posting at unusual times | 3am damage control |

## Market Validation Strategy

### Phase 1: Correlation Discovery
- Track all deltas
- Record market movements (price, volume, volatility)
- Find which delta types correlate with which movements
- Build initial confidence scores

### Phase 2: Predictive Testing
- When delta detected, record prediction
- Wait for market reaction
- Score prediction accuracy
- Refine model weights

### Phase 3: Real-time Validation
- Live alerts with confidence scores
- Track prediction success rate
- Continuous model improvement

### Validation Metrics

```python
class PredictionOutcome:
    delta_id: str
    delta_type: DeltaType
    entity: str
    confidence: float

    # Predictions made at detection time
    predicted_direction: str  # "up", "down", "volatile", "unchanged"
    predicted_magnitude: str  # "minor", "significant", "major"

    # Actual outcomes
    price_t0: float
    price_t1h: float
    price_t24h: float
    price_t7d: float

    # Scoring
    direction_correct: bool
    magnitude_correct: bool
    timing_accuracy: float
```

## Technology Stack

### Core Platform
- **Language**: Python 3.11+
- **Async Framework**: asyncio + aiohttp
- **Queue**: Redis Streams (real-time) + Kafka (persistence)

### Data Layer
- **Time-series**: TimescaleDB (discourse metrics over time)
- **Graph**: Neo4j (relationship/network analysis)
- **Vector Store**: Pinecone/Weaviate (semantic similarity)
- **Cache**: Redis

### ML/AI Layer
- **Embeddings**: OpenAI ada-002 or local sentence-transformers
- **LLM**: Claude API (analysis, classification, reasoning)
- **Topic Modeling**: BERTopic
- **Anomaly Detection**: Isolation Forest, LSTM autoencoders

### External APIs
- **X/Twitter**: API v2 (streaming + search)
- **Market Data**: Polygon.io, Alpha Vantage, or Yahoo Finance
- **News**: NewsAPI, GDELT (for context triggers)

## Directory Structure

```
MyPersona/
├── docs/
│   ├── architecture.md          # This document
│   ├── event_ontology.md        # Event type definitions
│   ├── delta_catalog.md         # Delta type specifications
│   └── api_specification.md     # API documentation
│
├── src/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py          # Configuration management
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── x_client.py          # X/Twitter API client
│   │   ├── stream_processor.py  # Real-time stream handling
│   │   └── preprocessor.py      # Cleaning, entity extraction
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── discourse.py         # Discourse state models
│   │   ├── expectation.py       # Expected state models
│   │   ├── delta.py             # Delta/gap models
│   │   ├── event.py             # Detected event models
│   │   └── market.py            # Market data models
│   │
│   ├── expectation/
│   │   ├── __init__.py
│   │   ├── baseline_builder.py  # Historical pattern analysis
│   │   ├── context_triggers.py  # Event-based expectation mods
│   │   └── generator.py         # Real-time expectation generation
│   │
│   ├── detection/
│   │   ├── __init__.py
│   │   ├── delta_detector.py    # Core gap detection
│   │   ├── analyzers/
│   │   │   ├── topic_absence.py
│   │   │   ├── voice_silence.py
│   │   │   ├── sentiment_decoupling.py
│   │   │   ├── network_break.py
│   │   │   └── volume_anomaly.py
│   │   └── classifier.py        # Event classification
│   │
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── market_tracker.py    # Price/volume tracking
│   │   ├── correlator.py        # Delta-market correlation
│   │   └── scorer.py            # Prediction scoring
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py            # LLM API wrapper
│   │   ├── prompts.py           # Prompt templates
│   │   └── reasoning.py         # LLM-based analysis
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── timeseries.py        # TimescaleDB interface
│   │   ├── graph.py             # Neo4j interface
│   │   ├── vector.py            # Vector store interface
│   │   └── event_store.py       # Unified event persistence
│   │
│   └── api/
│       ├── __init__.py
│       ├── routes.py            # API endpoints
│       └── websocket.py         # Real-time subscriptions
│
├── tests/
│   ├── __init__.py
│   ├── test_ingestion/
│   ├── test_expectation/
│   ├── test_detection/
│   └── test_validation/
│
├── scripts/
│   ├── backfill_baseline.py     # Build historical baselines
│   ├── run_stream.py            # Start real-time processing
│   └── validate_model.py        # Run validation analysis
│
├── config/
│   ├── default.yaml
│   ├── development.yaml
│   └── production.yaml
│
├── requirements.txt
├── pyproject.toml
├── Dockerfile
├── docker-compose.yaml
└── README.md
```

## Success Criteria

### Minimum Viable Proof
1. Detect at least 3 discourse deltas that precede market movements
2. Achieve >60% directional accuracy on predictions
3. Demonstrate deltas detected before price movement (lead time)

### Investor Demo Requirements
1. Live dashboard showing real-time delta detection
2. Historical backtest with clear correlation visualization
3. At least one "caught" event (detected before public knowledge)
4. Clear explanation of WHY the system works (not black box)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| X API rate limits | Can't get enough data | Multi-account strategy, prioritize high-value entities |
| Noise overwhelms signal | Too many false positives | Aggressive filtering, confidence thresholds |
| Market moves on non-discourse factors | Invalid correlation | Multi-factor awareness, humility in claims |
| Expectation model wrong | Missing real deltas | Continuous learning, human review loop |
| Latency too high | Miss the trade window | Edge deployment, stream processing |

## Next Steps

1. **Implement core data models** (discourse, expectation, delta)
2. **Build X ingestion pipeline** (API client, stream processor)
3. **Create baseline expectation builder** (historical analysis)
4. **Implement delta detectors** (start with topic absence, voice silence)
5. **Add market tracking** (price data integration)
6. **Build validation pipeline** (correlation analysis)
7. **Create demo dashboard** (visualization for investors)
