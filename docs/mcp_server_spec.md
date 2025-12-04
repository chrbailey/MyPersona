# MyPersona MCP Server: Technical Specification

## Overview

MyPersona is a Model Context Protocol (MCP) server that provides real-time contextual understanding of user intent to any LLM client. It fuses signals from sensors, location, time, and user profile to answer the question: **"What does this user REALLY need right now?"**

**Output:** Natural language context summary. No raw data leaves the device.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         EDGE DEVICE                             │
│                    (Phone, Watch, etc.)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    SIGNAL COLLECTORS                        ││
│  │                                                             ││
│  │  HealthKit ──┐                                              ││
│  │  CoreLocation ├──► SignalBus ──► SignalStore (in-memory)   ││
│  │  Calendar ────┤                                              ││
│  │  Contacts ────┤                                              ││
│  │  ScreenTime ──┘                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    INFERENCE ENGINE                         ││
│  │                                                             ││
│  │  SignalFusion ──► ContextInference ──► IntentDerivation    ││
│  │        │                  │                   │             ││
│  │        ▼                  ▼                   ▼             ││
│  │   Disambiguate      BiologicalModel     NeedsModel         ││
│  │   (HR+stairs vs     (Age→Drives)        (Maslow level)     ││
│  │    HR+social)                                               ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    MCP SERVER                               ││
│  │                                                             ││
│  │  Resources:                                                 ││
│  │    • persona://context       (current context)              ││
│  │    • persona://profile       (user profile)                 ││
│  │    • persona://quiet         (should system be quiet?)      ││
│  │                                                             ││
│  │  Tools:                                                     ││
│  │    • enrich_query(query) → enriched_query                   ││
│  │    • check_quiet_mode() → boolean                           ││
│  │    • get_response_style() → style_guidance                  ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│                              ▼ (JSON-RPC over stdio/HTTP)       │
└──────────────────────────────┼──────────────────────────────────┘
                               │
                               ▼
                    ┌───────────────────┐
                    │   ANY MCP CLIENT  │
                    │                   │
                    │  • Claude Desktop │
                    │  • ChatGPT        │
                    │  • Custom Apps    │
                    │  • IDE Assistants │
                    └───────────────────┘
```

---

## Data Structures

### SignalBundle

```typescript
interface SignalBundle {
  timestamp: number;  // Unix ms

  // Biometric (from HealthKit/Fitbit)
  biometric?: {
    heartRate: number;           // bpm
    heartRateVariability?: number;
    bloodPressure?: { systolic: number; diastolic: number };
    steps: number;               // last hour
    sleepHours?: number;         // last 24h
    bloodOxygen?: number;        // percentage
    skinTemperature?: number;    // celsius
  };

  // Location (from CoreLocation/GPS)
  location?: {
    latitude: number;
    longitude: number;
    altitude: number;
    speed: number;               // m/s
    altitudeChange: number;      // last 60 seconds
    placeType?: PlaceType;       // inferred or from Places API
    isHome: boolean;
    isWork: boolean;
    isFamiliar: boolean;
  };

  // Temporal
  temporal: {
    hour: number;                // 0-23
    dayOfWeek: number;           // 0-6
    isWeekend: boolean;
    isHoliday: boolean;
    calendarEvents: CalendarEvent[];  // next 2 hours
  };

  // Social (from proximity, contacts, etc.)
  social?: {
    nearbyDevices: number;       // Bluetooth/local network
    knownPeopleNearby: string[]; // Matched to contacts
    inConversation: boolean;     // Mic activity pattern
    lastInteraction?: {
      who: string;
      when: number;
      type: 'call' | 'message' | 'inPerson';
    };
  };

  // Device state
  device: {
    screenOn: boolean;
    activeApp?: string;
    audioPlaying: boolean;
    micActive: boolean;
    motionType: 'stationary' | 'walking' | 'running' | 'driving' | 'unknown';
  };
}

type PlaceType =
  | 'home' | 'work' | 'gym' | 'restaurant' | 'bar' | 'cafe'
  | 'store' | 'hospital' | 'school' | 'park' | 'transit'
  | 'entertainment' | 'religious' | 'unknown';
```

### UserProfile

```typescript
interface UserProfile {
  // Immutable/slow-changing
  birthYear: number;

  // Life stage (derived from age + signals over time)
  lifeStage: LifeStage;

  // Learned patterns
  patterns: {
    typicalWakeTime: number;     // hour
    typicalSleepTime: number;
    workDays: number[];          // [1,2,3,4,5] = Mon-Fri
    exercisePatterns: TimePattern[];
    socialPatterns: TimePattern[];
  };

  // Baseline biometrics (learned)
  baselines: {
    restingHeartRate: number;
    typicalSteps: number;        // per day
    typicalSleep: number;        // hours
  };

  // Survival memory (never forgets bad outcomes)
  memory: {
    trauma: Map<string, TraumaEvent>;      // Permanent
    warnings: Map<string, WarningEvent>;   // Slow decay
    baseline: Map<string, number>;         // Fast decay
  };
}

type LifeStage =
  | 'child'           // <13
  | 'adolescent'      // 13-17
  | 'young_adult'     // 18-25
  | 'adult'           // 26-40
  | 'middle_adult'    // 41-60
  | 'older_adult'     // 61-80
  | 'elder';          // 81+
```

### Context (Output)

```typescript
interface Context {
  // Current state
  state: {
    physical: 'resting' | 'active' | 'exercising' | 'sleeping';
    emotional: 'calm' | 'stressed' | 'excited' | 'anxious' | 'unknown';
    social: 'alone' | 'with_known' | 'with_unknown' | 'in_crowd';
    cognitive: 'focused' | 'relaxed' | 'distracted' | 'reflective';
  };

  // Biological drives (from life stage)
  drives: {
    primary: Drive;
    secondary: Drive[];
  };

  // Current need level (Maslow)
  needLevel: 'physiological' | 'safety' | 'belonging' | 'esteem' | 'actualization' | 'transcendence';

  // Mode
  mode: 'active' | 'quiet' | 'urgent';

  // Interpretation
  interpretation: string;        // Natural language

  // Response guidance
  responseStyle: {
    verbosity: 'minimal' | 'concise' | 'detailed';
    tone: 'casual' | 'professional' | 'supportive' | 'urgent';
    shouldProactivelyHelp: boolean;
    avoidTopics?: string[];
  };

  // Confidence
  confidence: number;            // 0.0 - 1.0
}

type Drive =
  | 'play'              // Child
  | 'identity'          // Adolescent
  | 'status'            // Young adult
  | 'mate_acquisition'  // Young adult
  | 'mate_retention'    // Adult
  | 'parental_care'     // Adult
  | 'career'            // Adult
  | 'legacy'            // Middle adult
  | 'comfort'           // Older adult
  | 'safety'            // Older adult
  | 'meaning'           // Elder
  | 'transcendence';    // Elder
```

---

## Core Algorithms

### 1. Signal Disambiguation

```typescript
function disambiguate(signals: SignalBundle, profile: UserProfile): State {
  const hr = signals.biometric?.heartRate ?? profile.baselines.restingHeartRate;
  const resting = profile.baselines.restingHeartRate;
  const elevated = hr > resting * 1.2;

  // Same signal, different meaning based on context
  if (elevated) {
    // Physical exertion?
    if (signals.location?.altitudeChange > 3) {
      return { physical: 'exercising', cause: 'stairs' };
    }
    if (signals.device.motionType === 'running') {
      return { physical: 'exercising', cause: 'running' };
    }

    // Social excitement?
    if (signals.location?.placeType === 'bar' && signals.temporal.isWeekend) {
      return { emotional: 'excited', cause: 'social' };
    }
    if (signals.social?.nearbyDevices > 0 && !signals.social?.knownPeopleNearby.length) {
      return { emotional: 'excited', cause: 'new_people' };
    }

    // Stress?
    if (signals.temporal.calendarEvents.some(e => e.type === 'meeting')) {
      return { emotional: 'stressed', cause: 'work' };
    }

    // Anxiety?
    if (signals.location?.isFamiliar === false && signals.temporal.hour > 22) {
      return { emotional: 'anxious', cause: 'unfamiliar_late' };
    }
  }

  return { physical: 'resting', emotional: 'calm' };
}
```

### 2. Biological Drive Inference

```typescript
function inferDrives(profile: UserProfile): DriveSet {
  const age = new Date().getFullYear() - profile.birthYear;

  // Evolutionary psychology: age → dominant drives
  const drivesByAge: Record<LifeStage, Drive[]> = {
    child:        ['play', 'affiliation'],
    adolescent:   ['identity', 'status', 'affiliation'],
    young_adult:  ['status', 'mate_acquisition', 'identity'],
    adult:        ['mate_retention', 'parental_care', 'career'],
    middle_adult: ['legacy', 'parental_care', 'career'],
    older_adult:  ['comfort', 'safety', 'legacy'],
    elder:        ['meaning', 'transcendence', 'comfort'],
  };

  return {
    primary: drivesByAge[profile.lifeStage][0],
    secondary: drivesByAge[profile.lifeStage].slice(1),
  };
}
```

### 3. Need Level Detection

```typescript
function detectNeedLevel(signals: SignalBundle, state: State): NeedLevel {
  // Physiological trumps all
  if (signals.biometric?.bloodOxygen && signals.biometric.bloodOxygen < 94) {
    return 'physiological';  // Urgent health
  }
  if (signals.biometric?.sleepHours && signals.biometric.sleepHours < 4) {
    return 'physiological';  // Sleep deprived
  }

  // Safety
  if (state.emotional === 'anxious') {
    return 'safety';
  }
  if (!signals.location?.isFamiliar && signals.temporal.hour > 23) {
    return 'safety';
  }

  // Belonging
  if (state.social === 'alone' && isTypicallySocialNow(signals, profile)) {
    return 'belonging';
  }
  if (state.emotional === 'excited' && state.social !== 'alone') {
    return 'belonging';
  }

  // Esteem
  if (signals.temporal.calendarEvents.some(e => e.type === 'presentation')) {
    return 'esteem';
  }
  if (state.social === 'with_unknown' && state.emotional === 'excited') {
    return 'esteem';  // Social performance context
  }

  // Actualization
  if (state.cognitive === 'focused' && signals.device.activeApp?.match(/creative|writing|code/)) {
    return 'actualization';
  }

  // Transcendence
  if (state.cognitive === 'reflective' && state.social === 'alone') {
    return 'transcendence';
  }

  return 'belonging';  // Default human need
}
```

### 4. Quiet Mode Detection

```typescript
function shouldBeQuiet(signals: SignalBundle, state: State): boolean {
  // Reflective moments - don't interrupt
  if (
    state.social === 'alone' &&
    state.cognitive === 'reflective' &&
    signals.device.motionType === 'stationary' &&
    !signals.device.screenOn
  ) {
    return true;
  }

  // Late night, calm, not actively using device
  if (
    signals.temporal.hour >= 22 &&
    state.emotional === 'calm' &&
    !signals.device.screenOn
  ) {
    return true;
  }

  // Recording voice note (like looking at moon)
  if (
    signals.device.micActive &&
    !signals.social?.inConversation &&
    state.social === 'alone'
  ) {
    return true;
  }

  // Sleeping or about to sleep
  if (state.physical === 'sleeping') {
    return true;
  }

  return false;
}
```

### 5. Context to Natural Language

```typescript
function contextToText(context: Context, query?: string): string {
  if (context.mode === 'quiet') {
    return '[User in reflective state. Respond only if directly asked. Keep response minimal.]';
  }

  const parts: string[] = [];

  // State description
  parts.push(`User state: ${describeState(context.state)}`);

  // Life stage and drives
  parts.push(`Life stage context: ${context.drives.primary} orientation`);

  // Current need
  parts.push(`Current priority: ${context.needLevel}-level needs`);

  // Interpretation
  parts.push(`Likely intent: ${context.interpretation}`);

  // Response guidance
  parts.push(`Suggested approach: ${context.responseStyle.tone}, ${context.responseStyle.verbosity}`);

  if (query) {
    parts.push(`\nWith this context, interpret: "${query}"`);
  }

  return parts.join('\n');
}

function describeState(state: Context['state']): string {
  const social = {
    'alone': 'alone',
    'with_known': 'with familiar people',
    'with_unknown': 'in social situation with new people',
    'in_crowd': 'in crowded environment',
  }[state.social];

  const emotional = state.emotional !== 'unknown' ? `, ${state.emotional}` : '';

  return `${state.physical}, ${social}${emotional}`;
}
```

---

## MCP Server Implementation

### Server Definition

```typescript
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';

const server = new Server(
  {
    name: 'mypersona',
    version: '1.0.0',
  },
  {
    capabilities: {
      resources: {},
      tools: {},
    },
  }
);
```

### Resources

```typescript
// Current context - the main resource
server.setRequestHandler(ListResourcesRequestSchema, async () => ({
  resources: [
    {
      uri: 'persona://context',
      name: 'Current User Context',
      description: 'Real-time contextual understanding of user state and intent',
      mimeType: 'text/plain',
    },
    {
      uri: 'persona://quiet',
      name: 'Quiet Mode Status',
      description: 'Whether the system should minimize interruptions',
      mimeType: 'application/json',
    },
  ],
}));

server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const uri = request.params.uri;

  if (uri === 'persona://context') {
    const signals = await gatherSignals();
    const context = inferContext(signals, userProfile);
    return {
      contents: [
        {
          uri,
          mimeType: 'text/plain',
          text: contextToText(context),
        },
      ],
    };
  }

  if (uri === 'persona://quiet') {
    const signals = await gatherSignals();
    const quiet = shouldBeQuiet(signals, inferState(signals));
    return {
      contents: [
        {
          uri,
          mimeType: 'application/json',
          text: JSON.stringify({ quiet, reason: quiet ? getQuietReason(signals) : null }),
        },
      ],
    };
  }

  throw new Error(`Unknown resource: ${uri}`);
});
```

### Tools

```typescript
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'enrich_query',
      description: 'Enrich a user query with contextual understanding',
      inputSchema: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'The raw user query',
          },
        },
        required: ['query'],
      },
    },
    {
      name: 'check_response_appropriate',
      description: 'Check if a proposed response is appropriate for current context',
      inputSchema: {
        type: 'object',
        properties: {
          response: {
            type: 'string',
            description: 'The proposed response',
          },
        },
        required: ['response'],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === 'enrich_query') {
    const signals = await gatherSignals();
    const context = inferContext(signals, userProfile);

    return {
      content: [
        {
          type: 'text',
          text: contextToText(context, args.query as string),
        },
      ],
    };
  }

  if (name === 'check_response_appropriate') {
    const signals = await gatherSignals();
    const context = inferContext(signals, userProfile);

    // Check if response matches context
    const appropriate = evaluateResponse(args.response as string, context);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(appropriate),
        },
      ],
    };
  }

  throw new Error(`Unknown tool: ${name}`);
});
```

### Transport

```typescript
// For Claude Desktop / local apps
async function runStdio() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

// For mobile / HTTP
async function runHttp(port: number) {
  const app = express();

  app.post('/mcp', async (req, res) => {
    const response = await server.handleRequest(req.body);
    res.json(response);
  });

  app.listen(port);
}
```

---

## Integration Examples

### Claude Desktop (claude_desktop_config.json)

```json
{
  "mcpServers": {
    "mypersona": {
      "command": "node",
      "args": ["/path/to/mypersona-server/dist/index.js"],
      "env": {
        "MYPERSONA_PROFILE": "/path/to/profile.json"
      }
    }
  }
}
```

### Custom App Integration

```typescript
import { Client } from '@modelcontextprotocol/sdk/client/index.js';

async function askWithContext(query: string): Promise<string> {
  // Get context from MyPersona
  const contextResult = await mcpClient.readResource({
    uri: 'persona://context',
  });
  const context = contextResult.contents[0].text;

  // Check quiet mode
  const quietResult = await mcpClient.readResource({
    uri: 'persona://quiet',
  });
  const { quiet } = JSON.parse(quietResult.contents[0].text);

  if (quiet && !isDirectQuestion(query)) {
    return null;  // Don't respond
  }

  // Send enriched query to LLM
  const response = await llm.complete({
    system: context,
    user: query,
  });

  return response;
}
```

### React Native / Mobile

```typescript
// Gather signals on mobile
async function gatherSignals(): Promise<SignalBundle> {
  const [health, location, calendar] = await Promise.all([
    HealthKit.getLatestHeartRate(),
    Geolocation.getCurrentPosition(),
    Calendar.getUpcomingEvents(2 * 60 * 60 * 1000),  // 2 hours
  ]);

  return {
    timestamp: Date.now(),
    biometric: {
      heartRate: health.heartRate,
      steps: health.stepCount,
    },
    location: {
      latitude: location.coords.latitude,
      longitude: location.coords.longitude,
      altitude: location.coords.altitude,
      speed: location.coords.speed,
      placeType: await inferPlaceType(location),
      isHome: isNearHome(location),
      isWork: isNearWork(location),
    },
    temporal: {
      hour: new Date().getHours(),
      dayOfWeek: new Date().getDay(),
      isWeekend: [0, 6].includes(new Date().getDay()),
      calendarEvents: calendar,
    },
    device: {
      screenOn: await DeviceInfo.isScreenOn(),
      motionType: await getMotionType(),
    },
  };
}
```

---

## Privacy Architecture

### What Stays on Device (EVERYTHING RAW)

- Heart rate values
- GPS coordinates
- Calendar details
- Contact names
- Conversation detection
- All sensor readings

### What Leaves Device (ONLY CONTEXT)

```
"User in social/romantic context, late night urban setting.
Asking about weather for potential outdoor continuation.
Response style: casual, concise, consider ambiance factors."
```

**The LLM never sees:**
- Your heart rate was 102
- You were at 37.7749, -122.4194
- "Sarah" was nearby
- You have a meeting at 9am

**The LLM only sees:**
- Inferred context
- Suggested response style
- What you likely mean

---

## File Structure

```
mypersona-mcp-server/
├── src/
│   ├── index.ts                 # Entry point
│   ├── server.ts                # MCP server setup
│   │
│   ├── signals/
│   │   ├── collector.ts         # Signal gathering
│   │   ├── types.ts             # Signal types
│   │   └── platforms/
│   │       ├── ios.ts           # HealthKit, CoreLocation
│   │       ├── android.ts       # Health Connect, Location
│   │       └── desktop.ts       # Limited signals
│   │
│   ├── inference/
│   │   ├── disambiguate.ts      # Same signal, different meaning
│   │   ├── biological.ts        # Age → drives
│   │   ├── needs.ts             # Maslow level detection
│   │   ├── quiet.ts             # When to shut up
│   │   └── context.ts           # Main inference pipeline
│   │
│   ├── profile/
│   │   ├── store.ts             # Profile persistence
│   │   ├── patterns.ts          # Pattern learning
│   │   └── memory.ts            # Trauma/warning/baseline
│   │
│   └── output/
│       ├── text.ts              # Context to natural language
│       └── validate.ts          # Response appropriateness
│
├── test/
│   ├── scenarios/               # Test scenarios
│   │   ├── saturday-night.ts
│   │   ├── work-meeting.ts
│   │   ├── quiet-moon.ts
│   │   └── family-morning.ts
│   └── disambiguation.test.ts
│
├── package.json
├── tsconfig.json
└── README.md
```

---

## Implementation Priority

### Phase 1: Core (Week 1-2)
- [ ] Basic MCP server structure
- [ ] Signal types defined
- [ ] Mock signal generation for testing
- [ ] Simple context inference
- [ ] Text output generation

### Phase 2: Signals (Week 3-4)
- [ ] iOS HealthKit integration
- [ ] Location services
- [ ] Calendar integration
- [ ] Time/temporal context

### Phase 3: Intelligence (Week 5-6)
- [ ] Disambiguation logic
- [ ] Biological drive model
- [ ] Need level detection
- [ ] Quiet mode detection

### Phase 4: Memory (Week 7-8)
- [ ] Pattern learning
- [ ] Profile persistence
- [ ] Survival memory (trauma/warning/baseline)

### Phase 5: Polish (Week 9-10)
- [ ] Response validation
- [ ] Edge case handling
- [ ] Performance optimization
- [ ] Privacy audit

---

## The Test

When complete, this should work:

**User:** "What's the weather?"

**MyPersona Context (internal, 50ms):**
```
User state: active, with new people, excited
Life stage context: mate_acquisition orientation
Current priority: esteem-level needs
Likely intent: Considering leaving venue with someone,
               wants to know if outdoor walk is viable
Suggested approach: casual, concise
```

**LLM Response:**
```
"Nice night - 65°, clear. The waterfront's about 10 minutes away."
```

**User never explained. MyPersona inferred. LLM delivered.**

---

## License Consideration

The MCP server code can be open source.
The inference rules (disambiguation, biological model, needs detection) are the IP.
Consider dual-licensing: open core + proprietary inference engine.
