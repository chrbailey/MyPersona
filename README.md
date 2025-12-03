# MyPersona: Discourse Delta Detection System

> **Detecting market-moving events by analyzing what ISN'T being said**

MyPersona is a real-time event detection system that identifies market-relevant events by analyzing the **gap between expected discourse and actual discourse** on social platforms. When people collectively avoid discussing something they normally would, or when expected communication patterns break, something significant is happening.

## The Core Innovation

Most sentiment analysis asks: *"What are people saying?"*

We ask: **"What SHOULD people be saying right now that they're NOT?"**

This delta - the gap between expected and observed discourse - is often a leading indicator of significant events.

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DISCOURSE DELTA ENGINE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │   X/Twitter  │    │  Expectation │    │    Delta     │    │  Market   │ │
│  │   Ingestion  │───▶│    Model     │───▶│  Detection   │───▶│ Validator │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│                                                                             │
│  What IS being said   What SHOULD be     The Gap Between    Does it predict│
│                       said (baseline)    Expected/Actual    market moves?  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Delta Types We Detect

| Delta Type | Description | Example Signal |
|------------|-------------|----------------|
| **Topic Absence** | Expected topic not mentioned | Company stops mentioning key product |
| **Voice Silence** | Usually active account goes quiet | CEO silent during crisis |
| **Sentiment Decoupling** | Tone doesn't match news | Positive news, negative undertone |
| **Volume Collapse** | Sudden drop in discussion | Coordinated non-discussion |
| **Network Break** | Expected responses not happening | Usual defenders absent |
| **Coordinated Silence** | Multiple voices go quiet together | Pre-announcement quiet |

## Market Validation

The system validates its predictions against actual market movements:

- Track all detected deltas
- Record market movements at multiple time horizons (1h, 4h, 24h, 1w)
- Correlate delta types with price movements
- Build confidence scores based on historical accuracy

**If discourse deltas consistently precede market movements, the system works.**

## Project Structure

```
MyPersona/
├── docs/
│   └── architecture.md      # Full system architecture
├── src/
│   ├── config/              # Configuration management
│   ├── ingestion/           # X/Twitter data ingestion
│   ├── models/              # Core data models
│   ├── expectation/         # "What should be said" engine
│   ├── detection/           # Delta detection & classification
│   ├── validation/          # Market correlation validation
│   ├── llm/                 # LLM integration (Claude)
│   └── storage/             # Persistence layer
├── scripts/
│   └── run_stream.py        # Main runner script
├── config/
│   └── default.yaml         # Default configuration
├── requirements.txt
└── pyproject.toml
```

## Quick Start

### Prerequisites

- Python 3.11+
- X/Twitter API access (Bearer token)
- Anthropic API key (for Claude)
- Market data API key (Polygon.io recommended)

### Installation

```bash
# Clone the repository
git clone https://github.com/mypersona/mypersona.git
cd mypersona

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Set environment variables:

```bash
export X_BEARER_TOKEN="your_twitter_bearer_token"
export ANTHROPIC_API_KEY="your_anthropic_api_key"
export MARKET_DATA_API_KEY="your_polygon_api_key"
```

Or configure in `config/default.yaml`.

### Running

```bash
# Start the stream processor
python scripts/run_stream.py
```

## Use Cases

1. **Investment Signal Generation**: Detect events before they become public knowledge
2. **Risk Monitoring**: Identify emerging crises from discourse patterns
3. **Competitive Intelligence**: Track when competitors go quiet about key topics
4. **Insider Activity Detection**: Identify unusual communication patterns

## Investor Demo Goals

1. Achieve >60% directional accuracy on market predictions
2. Demonstrate lead time before price movements
3. Show at least 3 "caught" events (detected before public knowledge)
4. Provide clear, non-black-box explanations

## Technology Stack

- **Python 3.11+** - Core language
- **aiohttp** - Async HTTP client for API calls
- **Claude (Anthropic)** - LLM for deep reasoning
- **Redis** - Caching and real-time queues
- **TimescaleDB** - Time-series storage (production)
- **Neo4j** - Relationship/network analysis (production)

## License

MIT License - see LICENSE file for details.

## Status

**Current Phase**: Architecture Complete, Ready for Data Integration

The core system is designed and implemented. Next steps:
1. Connect live X/Twitter data source
2. Build historical baselines for target entities
3. Begin validation tracking
4. Iterate based on prediction accuracy
