# Delta Filter: iPhone MVP Technical Specification

## Executive Summary

A real-time audio/text analysis app that detects **what ISN'T being said** compared to what SHOULD be said, and surfaces those gaps (deltas) to the user in real-time.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           iPHONE APP ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐ │
│  │   CAPTURE   │   │  TRANSCRIBE │   │   ANALYZE   │   │     DISPLAY     │ │
│  │   MODULE    │──▶│   MODULE    │──▶│   MODULE    │──▶│     MODULE      │ │
│  │             │   │             │   │             │   │                 │ │
│  │ Microphone  │   │ Speech-to-  │   │ Delta       │   │ Real-time UI    │ │
│  │ Audio Queue │   │ Text Engine │   │ Detection   │   │ Notifications   │ │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────────┘ │
│         │                 │                 │                   │          │
│         └─────────────────┴────────┬────────┴───────────────────┘          │
│                                    │                                        │
│                                    ▼                                        │
│                    ┌───────────────────────────────┐                        │
│                    │      BACKEND SERVICES         │                        │
│                    │                               │                        │
│                    │  • Expectation Engine (API)   │                        │
│                    │  • LLM Analysis (Claude API)  │                        │
│                    │  • User Context Storage       │                        │
│                    └───────────────────────────────┘                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## MODULE 1: Audio Capture Module

### Purpose
Continuously capture audio from iPhone microphone, buffer it, and stream to transcription.

### Technical Requirements

| Requirement | Specification |
|-------------|---------------|
| Framework | AVFoundation (AVAudioEngine) |
| Sample Rate | 16kHz (speech optimized) |
| Buffer Size | 100ms chunks |
| Format | Linear PCM, mono |
| Background Mode | Yes (requires entitlement) |
| Privacy | Microphone permission required |

### Interface Contract

```swift
// AudioCaptureModule.swift

protocol AudioCaptureDelegate: AnyObject {
    func audioCaptureDidReceiveBuffer(_ buffer: AVAudioPCMBuffer, time: AVAudioTime)
    func audioCaptureDidEncounterError(_ error: AudioCaptureError)
    func audioCaptureDidChangeState(_ state: CaptureState)
}

enum CaptureState {
    case idle
    case recording
    case paused
    case error(AudioCaptureError)
}

enum AudioCaptureError: Error {
    case microphonePermissionDenied
    case audioSessionSetupFailed
    case hardwareNotAvailable
    case interruptedBySystem
}

protocol AudioCaptureModuleProtocol {
    var delegate: AudioCaptureDelegate? { get set }
    var isRecording: Bool { get }
    var currentState: CaptureState { get }

    func requestPermission() async -> Bool
    func startCapture() throws
    func stopCapture()
    func pauseCapture()
    func resumeCapture()
}
```

### Data Output

```swift
struct AudioChunk {
    let id: UUID
    let timestamp: Date
    let duration: TimeInterval  // ~100ms
    let samples: Data           // PCM audio data
    let sampleRate: Int         // 16000
    let channels: Int           // 1 (mono)
}
```

### Developer Handoff Notes
- **Scope**: iOS audio capture only
- **Does NOT include**: Transcription, analysis, or UI
- **Test criteria**: Can record 1 hour continuously without memory leak
- **Privacy**: Must handle interruptions (calls, Siri, etc.)

---

## MODULE 2: Transcription Module

### Purpose
Convert streaming audio to text with word-level timestamps and speaker identification.

### Technical Options

| Option | Latency | Accuracy | Cost | Offline |
|--------|---------|----------|------|---------|
| Apple Speech Framework | ~200ms | Good | Free | Yes |
| Whisper (on-device) | ~500ms | Excellent | Free | Yes |
| Deepgram API | ~100ms | Excellent | $0.0043/min | No |
| AssemblyAI API | ~150ms | Excellent | $0.0042/min | No |

### Recommended: Hybrid Approach
- **Primary**: On-device Apple Speech (free, low latency, offline)
- **Fallback**: Cloud API for accuracy-critical mode

### Interface Contract

```swift
// TranscriptionModule.swift

protocol TranscriptionDelegate: AnyObject {
    func transcriptionDidReceivePartial(_ result: PartialTranscript)
    func transcriptionDidReceiveFinal(_ result: FinalTranscript)
    func transcriptionDidEncounterError(_ error: TranscriptionError)
}

struct PartialTranscript {
    let sessionId: UUID
    let text: String
    let confidence: Float       // 0.0 - 1.0
    let isFinal: Bool
    let timestamp: Date
}

struct FinalTranscript {
    let sessionId: UUID
    let text: String
    let words: [TranscribedWord]
    let speakers: [SpeakerSegment]?
    let duration: TimeInterval
    let timestamp: Date
}

struct TranscribedWord {
    let word: String
    let startTime: TimeInterval
    let endTime: TimeInterval
    let confidence: Float
    let speakerId: String?
}

struct SpeakerSegment {
    let speakerId: String
    let label: String           // "Speaker 1", "CEO", etc.
    let startTime: TimeInterval
    let endTime: TimeInterval
}

protocol TranscriptionModuleProtocol {
    var delegate: TranscriptionDelegate? { get set }
    var isTranscribing: Bool { get }

    func configure(options: TranscriptionOptions)
    func startTranscription(sessionId: UUID)
    func processAudioChunk(_ chunk: AudioChunk)
    func stopTranscription()
}

struct TranscriptionOptions {
    let language: String            // "en-US"
    let enableSpeakerDiarization: Bool
    let enablePunctuation: Bool
    let useCloudFallback: Bool
    let cloudProvider: CloudTranscriptionProvider?
}
```

### Developer Handoff Notes
- **Scope**: Audio-to-text only
- **Does NOT include**: Audio capture, delta analysis
- **Input**: AudioChunk stream
- **Output**: TranscribedWord stream with timestamps
- **Test criteria**: <300ms latency, >90% accuracy on clear speech

---

## MODULE 3: Context Manager Module

### Purpose
Manage session context, user-defined expectations, and domain configurations.

### What This Module Does
- Stores what the user EXPECTS to hear (topics, speakers, terms)
- Loads pre-built domain templates (earnings call, interview, etc.)
- Tracks what HAS been said in current session
- Provides context to the Analysis module

### Interface Contract

```swift
// ContextManagerModule.swift

struct SessionContext {
    let sessionId: UUID
    let sessionType: SessionType
    let startTime: Date
    let domain: DomainConfig

    // What we expect
    var expectedTopics: [ExpectedTopic]
    var expectedSpeakers: [ExpectedSpeaker]
    var expectedPhrases: [ExpectedPhrase]

    // What we've observed
    var observedTopics: [ObservedTopic]
    var observedSpeakers: [ObservedSpeaker]
    var transcriptSoFar: String
    var wordCount: Int
    var elapsedTime: TimeInterval
}

enum SessionType: String, Codable {
    case earningsCall
    case interview
    case meeting
    case negotiation
    case presentation
    case custom
}

struct DomainConfig: Codable {
    let id: String
    let name: String
    let description: String

    // Expected topic templates
    let defaultExpectedTopics: [TopicTemplate]

    // Typical phrases that should appear
    let expectedPhrasePatterns: [String]

    // Key roles/speakers
    let expectedRoles: [String]

    // Time expectations
    let typicalDurationMinutes: Int
    let topicTimingExpectations: [TopicTiming]
}

struct ExpectedTopic {
    let id: UUID
    let name: String
    let keywords: [String]
    let importance: Float           // 0.0 - 1.0
    let expectedByMinute: Int?      // nil = anytime
    let isRequired: Bool
    var hasBeenMentioned: Bool
    var lastMentionedAt: Date?
    var mentionCount: Int
}

struct ExpectedSpeaker {
    let id: UUID
    let role: String                // "CEO", "Interviewer", etc.
    let expectedSpeakingRatio: Float // 0.0 - 1.0
    var actualSpeakingRatio: Float
    var lastSpokeAt: Date?
    var totalSpeakingTime: TimeInterval
}

struct ObservedTopic {
    let topicId: UUID?              // Links to ExpectedTopic if matched
    let name: String
    let firstMentionedAt: Date
    let lastMentionedAt: Date
    let mentionCount: Int
    let sentiment: Float            // -1.0 to 1.0
}

protocol ContextManagerProtocol {
    // Session management
    func createSession(type: SessionType, domain: DomainConfig?) -> SessionContext
    func getSession(_ sessionId: UUID) -> SessionContext?
    func updateSession(_ sessionId: UUID, with update: SessionUpdate)
    func endSession(_ sessionId: UUID)

    // Domain configs
    func getAvailableDomains() -> [DomainConfig]
    func getDomain(_ id: String) -> DomainConfig?
    func createCustomDomain(_ config: DomainConfig) -> String

    // Expectations
    func addExpectedTopic(_ topic: ExpectedTopic, to sessionId: UUID)
    func removeExpectedTopic(_ topicId: UUID, from sessionId: UUID)
    func addExpectedSpeaker(_ speaker: ExpectedSpeaker, to sessionId: UUID)

    // Observations
    func recordTopicMention(_ topicName: String, in sessionId: UUID, at time: Date)
    func recordSpeakerActivity(_ speakerId: String, duration: TimeInterval, in sessionId: UUID)
    func appendTranscript(_ text: String, to sessionId: UUID)
}

enum SessionUpdate {
    case topicMentioned(topicId: UUID, at: Date)
    case speakerSpoke(speakerId: String, duration: TimeInterval)
    case transcriptAppended(text: String)
    case observedNewTopic(name: String)
}
```

### Pre-Built Domain Configs (Examples)

```swift
// DomainConfigs.swift

let earningsCallDomain = DomainConfig(
    id: "earnings_call",
    name: "Earnings Call",
    description: "Quarterly earnings conference call",
    defaultExpectedTopics: [
        TopicTemplate(name: "Revenue", keywords: ["revenue", "sales", "top line"], importance: 0.95),
        TopicTemplate(name: "Earnings Per Share", keywords: ["eps", "earnings per share", "profit"], importance: 0.95),
        TopicTemplate(name: "Guidance", keywords: ["guidance", "outlook", "forecast", "expect"], importance: 0.9),
        TopicTemplate(name: "Margins", keywords: ["margin", "gross margin", "operating margin"], importance: 0.85),
        TopicTemplate(name: "Cash Flow", keywords: ["cash flow", "free cash flow", "fcf"], importance: 0.8),
        TopicTemplate(name: "Debt", keywords: ["debt", "leverage", "borrowing"], importance: 0.7),
        TopicTemplate(name: "Competition", keywords: ["competitor", "competition", "market share"], importance: 0.6),
    ],
    expectedRoles: ["CEO", "CFO", "Analyst"],
    typicalDurationMinutes: 60
)

let jobInterviewDomain = DomainConfig(
    id: "job_interview",
    name: "Job Interview",
    description: "Candidate interview session",
    defaultExpectedTopics: [
        TopicTemplate(name: "Experience", keywords: ["experience", "worked", "previous role"], importance: 0.9),
        TopicTemplate(name: "Skills", keywords: ["skills", "proficient", "expertise"], importance: 0.85),
        TopicTemplate(name: "Teamwork", keywords: ["team", "collaborate", "together"], importance: 0.8),
        TopicTemplate(name: "Challenges", keywords: ["challenge", "difficult", "problem", "conflict"], importance: 0.8),
        TopicTemplate(name: "Goals", keywords: ["goal", "ambition", "future", "growth"], importance: 0.75),
        TopicTemplate(name: "Salary", keywords: ["salary", "compensation", "pay", "benefits"], importance: 0.7),
        TopicTemplate(name: "Questions", keywords: ["question for us", "ask us", "want to know"], importance: 0.65),
    ],
    expectedRoles: ["Interviewer", "Candidate"],
    typicalDurationMinutes: 45
)

let negotiationDomain = DomainConfig(
    id: "negotiation",
    name: "Negotiation",
    description: "Business or sales negotiation",
    defaultExpectedTopics: [
        TopicTemplate(name: "Price", keywords: ["price", "cost", "budget", "afford"], importance: 0.95),
        TopicTemplate(name: "Timeline", keywords: ["timeline", "when", "deadline", "schedule"], importance: 0.85),
        TopicTemplate(name: "Terms", keywords: ["terms", "conditions", "contract"], importance: 0.85),
        TopicTemplate(name: "Competition", keywords: ["other options", "alternatives", "competitor"], importance: 0.8),
        TopicTemplate(name: "Decision Maker", keywords: ["decision", "approve", "sign off", "authority"], importance: 0.75),
        TopicTemplate(name: "Objections", keywords: ["concern", "worried", "issue", "problem"], importance: 0.7),
    ],
    expectedRoles: ["Seller", "Buyer"],
    typicalDurationMinutes: 30
)
```

### Developer Handoff Notes
- **Scope**: State management and configuration only
- **Does NOT include**: Audio, transcription, or delta detection logic
- **Storage**: CoreData or UserDefaults for persistence
- **Test criteria**: Can create/update/query sessions with <10ms latency

---

## MODULE 4: Delta Detection Engine

### Purpose
Compare observed discourse to expected discourse and identify gaps (deltas).

### This Is The Core Innovation
This module is the "secret sauce" - it determines WHAT'S MISSING.

### Interface Contract

```swift
// DeltaDetectionEngine.swift

protocol DeltaDetectionDelegate: AnyObject {
    func deltaEngineDidDetect(_ delta: DetectedDelta)
    func deltaEngineDidUpdateStatus(_ status: AnalysisStatus)
}

struct DetectedDelta {
    let id: UUID
    let deltaType: DeltaType
    let severity: DeltaSeverity
    let confidence: Float           // 0.0 - 1.0
    let detectedAt: Date

    // What we expected
    let expectedDescription: String

    // What we observed (or didn't)
    let observedDescription: String

    // Human-readable alert
    let alertTitle: String
    let alertDetail: String

    // Source evidence
    let relevantTranscript: String?
    let timeInSession: TimeInterval
}

enum DeltaType: String {
    case topicAbsence           // Expected topic not mentioned
    case topicAvoidance         // Topic mentioned then dropped
    case speakerSilence         // Expected speaker not talking
    case toneShift              // Sentiment/tone changed
    case questionDodge          // Direct question not answered
    case timeAnomaly            // Topic mentioned too late/early
    case repetitionAnomaly      // Same thing repeated unusually
    case hedgingDetected        // Unusual hedging language
}

enum DeltaSeverity: String {
    case low                    // Minor deviation
    case medium                 // Notable, worth flagging
    case high                   // Significant gap
    case critical               // Major red flag
}

struct AnalysisStatus {
    let sessionId: UUID
    let elapsedTime: TimeInterval
    let wordsAnalyzed: Int
    let deltasDetected: Int
    let topicsExpected: Int
    let topicsMentioned: Int
    let coveragePercentage: Float
}

protocol DeltaDetectionEngineProtocol {
    var delegate: DeltaDetectionDelegate? { get set }

    func configure(with context: SessionContext)
    func processTranscript(_ transcript: FinalTranscript)
    func processPartialTranscript(_ partial: PartialTranscript)
    func getCurrentStatus() -> AnalysisStatus
    func getDetectedDeltas() -> [DetectedDelta]
    func reset()
}
```

### Detection Logic (Pseudo-code)

```swift
// DeltaDetectionLogic.swift (INTERNAL - do not share with module developers)

class DeltaDetector {

    func analyzeForDeltas(context: SessionContext, newTranscript: String) -> [DetectedDelta] {
        var deltas: [DetectedDelta] = []

        // 1. CHECK TOPIC ABSENCE
        // For each expected topic that hasn't been mentioned:
        //   - Calculate time into session
        //   - If past expected mention time, flag as delta
        //   - Severity based on importance and time elapsed

        for topic in context.expectedTopics where !topic.hasBeenMentioned {
            let minutesElapsed = context.elapsedTime / 60

            if let expectedBy = topic.expectedByMinute, minutesElapsed > Double(expectedBy) {
                let delta = DetectedDelta(
                    deltaType: .topicAbsence,
                    severity: calculateSeverity(importance: topic.importance,
                                                 overdue: minutesElapsed - Double(expectedBy)),
                    alertTitle: "'\(topic.name)' not yet mentioned",
                    alertDetail: "Usually discussed by minute \(expectedBy). Now at minute \(Int(minutesElapsed))."
                )
                deltas.append(delta)
            }
        }

        // 2. CHECK SPEAKER SILENCE
        // For each expected speaker:
        //   - Compare actual vs expected speaking ratio
        //   - Flag if significantly below expected

        for speaker in context.expectedSpeakers {
            let ratio = speaker.actualSpeakingRatio / speaker.expectedSpeakingRatio
            if ratio < 0.3 && context.elapsedTime > 300 { // 5 min minimum
                let delta = DetectedDelta(
                    deltaType: .speakerSilence,
                    severity: .medium,
                    alertTitle: "\(speaker.role) unusually quiet",
                    alertDetail: "Speaking \(Int(speaker.actualSpeakingRatio * 100))% vs expected \(Int(speaker.expectedSpeakingRatio * 100))%"
                )
                deltas.append(delta)
            }
        }

        // 3. CHECK FOR QUESTION DODGES (requires LLM)
        // Send recent Q&A exchange to LLM:
        //   - Was the question directly answered?
        //   - Was there deflection or pivot?

        // 4. CHECK FOR TONE SHIFTS (requires LLM)
        // Compare sentiment of last 2 minutes vs session average:
        //   - Significant negative shift = flag
        //   - Defensive language appearing = flag

        // 5. CHECK FOR HEDGING LANGUAGE
        // Pattern match for hedging phrases:
        //   - "I think", "maybe", "possibly", "we'll see"
        //   - Frequency spike = flag

        return deltas
    }
}
```

### LLM Integration Points

The Delta Engine needs LLM calls for nuanced detection:

```swift
// LLMAnalysisRequests.swift

struct QuestionDodgeAnalysisRequest {
    let question: String
    let response: String
    let context: String
}

struct QuestionDodgeAnalysisResponse: Codable {
    let wasDirectlyAnswered: Bool
    let confidence: Float
    let evasionType: String?        // "pivot", "deflection", "partial", "none"
    let explanation: String
}

struct ToneAnalysisRequest {
    let recentTranscript: String    // Last ~2 minutes
    let sessionTranscript: String   // Full session
    let speakerRole: String?
}

struct ToneAnalysisResponse: Codable {
    let currentTone: String         // "confident", "defensive", "uncertain", etc.
    let baselineTone: String
    let shiftDetected: Bool
    let shiftSeverity: Float
    let explanation: String
}
```

### Developer Handoff Notes
- **Scope**: Delta detection logic only
- **Inputs**: SessionContext + Transcript stream
- **Outputs**: DetectedDelta stream
- **Dependencies**: Needs LLM API access for advanced detection
- **CRITICAL**: This module contains core IP - limit access

---

## MODULE 5: LLM Service Module

### Purpose
Abstract LLM API calls for analysis tasks.

### Interface Contract

```swift
// LLMServiceModule.swift

protocol LLMServiceProtocol {
    func analyzeQuestionDodge(_ request: QuestionDodgeAnalysisRequest) async throws -> QuestionDodgeAnalysisResponse
    func analyzeTone(_ request: ToneAnalysisRequest) async throws -> ToneAnalysisResponse
    func extractTopics(from text: String) async throws -> [ExtractedTopic]
    func classifyIntent(_ text: String) async throws -> IntentClassification
}

struct LLMServiceConfig {
    let provider: LLMProvider
    let apiKey: String
    let model: String
    let maxTokensPerRequest: Int
    let timeoutSeconds: TimeInterval
}

enum LLMProvider {
    case anthropic      // Claude
    case openai         // GPT-4
    case local          // On-device (future)
}

struct ExtractedTopic {
    let name: String
    let confidence: Float
    let sentiment: Float
    let keywords: [String]
}

struct IntentClassification {
    let primaryIntent: String
    let confidence: Float
    let isQuestion: Bool
    let isAnswer: Bool
    let isDeflection: Bool
}
```

### Rate Limiting & Cost Control

```swift
struct LLMUsageTracker {
    var requestsThisMinute: Int
    var requestsThisSession: Int
    var tokensUsedThisSession: Int
    var estimatedCostThisSession: Decimal

    let maxRequestsPerMinute: Int = 20
    let maxCostPerSession: Decimal = 1.00  // $1 max per session
}
```

### Developer Handoff Notes
- **Scope**: API wrapper only
- **Does NOT include**: Prompt engineering (that's in Delta Engine)
- **Test criteria**: Handle rate limits gracefully, retry on failure
- **Security**: API keys must not be in client code (use backend proxy)

---

## MODULE 6: UI/Display Module

### Purpose
Real-time display of deltas and session status.

### Screen Layouts

```
┌─────────────────────────────────────────┐
│  MAIN SESSION VIEW                      │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────────────────────────────┐    │
│  │     SESSION STATUS BAR          │    │
│  │  🎙 Recording  |  12:34  |  ●●○  │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │     DELTA ALERT CARDS           │    │
│  │                                 │    │
│  │  ⚠️ HIGH                        │    │
│  │  "Guidance" not mentioned       │    │
│  │  Expected by minute 15          │    │
│  │  ─────────────────────────────  │    │
│  │                                 │    │
│  │  ℹ️ MEDIUM                      │    │
│  │  CFO speaking less than usual   │    │
│  │  12% vs expected 30%            │    │
│  │                                 │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │     TOPIC COVERAGE              │    │
│  │                                 │    │
│  │  ✓ Revenue          mentioned   │    │
│  │  ✓ EPS              mentioned   │    │
│  │  ○ Guidance         waiting...  │    │
│  │  ○ Margins          waiting...  │    │
│  │  ○ Competition      waiting...  │    │
│  │                                 │    │
│  │  Coverage: 40% ████░░░░░░       │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │     LIVE TRANSCRIPT (optional)  │    │
│  │                                 │    │
│  │  "...and our revenue for Q3..." │    │
│  └─────────────────────────────────┘    │
│                                         │
│  [  ⏸ Pause  ]    [  ⏹ End Session  ]  │
│                                         │
└─────────────────────────────────────────┘
```

### UI Components

```swift
// UIComponents.swift

struct SessionStatusBar: View {
    let isRecording: Bool
    let elapsedTime: TimeInterval
    let signalStrength: SignalStrength  // Audio quality indicator
}

struct DeltaAlertCard: View {
    let delta: DetectedDelta
    let onTap: () -> Void
    let onDismiss: () -> Void
}

struct TopicCoverageList: View {
    let expectedTopics: [ExpectedTopic]
    let observedTopics: [ObservedTopic]
}

struct CoverageProgressBar: View {
    let percentage: Float
    let label: String
}

struct LiveTranscriptView: View {
    let recentText: String
    let highlightedKeywords: [String]
}
```

### Haptic & Audio Feedback

```swift
enum AlertFeedback {
    case lowDelta       // Subtle haptic
    case mediumDelta    // Medium haptic
    case highDelta      // Strong haptic + optional sound
    case criticalDelta  // Strong haptic + sound + screen flash
}

class FeedbackManager {
    func triggerFeedback(for severity: DeltaSeverity)
    func configureFeedback(haptics: Bool, sounds: Bool, visual: Bool)
}
```

### Developer Handoff Notes
- **Scope**: SwiftUI views and navigation only
- **Does NOT include**: Business logic
- **Input**: ViewModel with published properties
- **Test criteria**: 60fps scrolling, instant haptic response
- **Accessibility**: VoiceOver support required

---

## MODULE 7: Backend API Service

### Purpose
Server-side components that can't run on device.

### Endpoints

```yaml
# API Specification

POST /api/v1/sessions
  Description: Create new analysis session
  Request:
    - user_id: string
    - session_type: string
    - domain_config: object (optional)
  Response:
    - session_id: uuid
    - api_key: string (temporary, for this session)

POST /api/v1/sessions/{session_id}/analyze
  Description: Send transcript chunk for analysis
  Request:
    - transcript: string
    - timestamp: datetime
    - context_update: object (optional)
  Response:
    - deltas: array[Delta]
    - status: AnalysisStatus

GET /api/v1/sessions/{session_id}/deltas
  Description: Get all deltas for session
  Response:
    - deltas: array[Delta]
    - summary: object

POST /api/v1/llm/analyze
  Description: Proxy to LLM API (keeps API keys server-side)
  Request:
    - analysis_type: string
    - payload: object
  Response:
    - result: object

GET /api/v1/domains
  Description: Get available domain configurations
  Response:
    - domains: array[DomainConfig]

POST /api/v1/domains
  Description: Create custom domain config
  Request:
    - domain: DomainConfig
  Response:
    - domain_id: string
```

### Why Backend Is Needed

| Function | Why Not On-Device |
|----------|-------------------|
| LLM API proxy | Keep API keys secure |
| Session storage | Persist across devices |
| Domain configs | Share/update centrally |
| Usage tracking | Billing, rate limiting |
| Model updates | Update detection logic without app update |

### Developer Handoff Notes
- **Scope**: REST API only
- **Does NOT include**: iOS code
- **Stack suggestion**: Python FastAPI or Node.js
- **Hosting**: AWS Lambda + API Gateway or similar
- **Security**: JWT auth, rate limiting, input validation

---

## MODULE 8: Data Persistence Module

### Purpose
Local storage on device for sessions, settings, and offline support.

### Data Models (CoreData)

```swift
// CoreData Entities

@objc(SessionEntity)
class SessionEntity: NSManagedObject {
    @NSManaged var id: UUID
    @NSManaged var type: String
    @NSManaged var domainId: String?
    @NSManaged var startTime: Date
    @NSManaged var endTime: Date?
    @NSManaged var transcript: String
    @NSManaged var deltasJSON: Data      // Serialized [DetectedDelta]
    @NSManaged var statusJSON: Data      // Serialized AnalysisStatus
}

@objc(DomainConfigEntity)
class DomainConfigEntity: NSManagedObject {
    @NSManaged var id: String
    @NSManaged var name: String
    @NSManaged var configJSON: Data      // Serialized DomainConfig
    @NSManaged var isBuiltIn: Bool
    @NSManaged var lastUsed: Date?
}

@objc(UserSettingsEntity)
class UserSettingsEntity: NSManagedObject {
    @NSManaged var userId: String
    @NSManaged var hapticsEnabled: Bool
    @NSManaged var soundsEnabled: Bool
    @NSManaged var showTranscript: Bool
    @NSManaged var defaultDomainId: String?
    @NSManaged var subscriptionTier: String
}
```

### Developer Handoff Notes
- **Scope**: CoreData setup and CRUD operations
- **Does NOT include**: Business logic
- **Test criteria**: Handle 100+ sessions without performance degradation

---

## INTEGRATION: How Modules Connect

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              APP COORDINATOR                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌────────────┐                                                             │
│   │   USER     │                                                             │
│   │   TAPS     │                                                             │
│   │  "START"   │                                                             │
│   └─────┬──────┘                                                             │
│         │                                                                    │
│         ▼                                                                    │
│   ┌────────────┐     ┌────────────┐                                         │
│   │  CONTEXT   │────▶│   AUDIO    │                                         │
│   │  MANAGER   │     │  CAPTURE   │                                         │
│   │            │     │            │                                         │
│   │ Create     │     │ Start      │                                         │
│   │ Session    │     │ Recording  │                                         │
│   └────────────┘     └─────┬──────┘                                         │
│                            │                                                 │
│                            │ AudioChunk                                      │
│                            ▼                                                 │
│                      ┌────────────┐                                         │
│                      │TRANSCRIBE  │                                         │
│                      │            │                                         │
│                      │ Speech →   │                                         │
│                      │ Text       │                                         │
│                      └─────┬──────┘                                         │
│                            │                                                 │
│                            │ FinalTranscript                                │
│                            ▼                                                 │
│   ┌────────────┐     ┌────────────┐     ┌────────────┐                      │
│   │  CONTEXT   │◀───▶│   DELTA    │────▶│    LLM     │                      │
│   │  MANAGER   │     │  DETECTION │     │  SERVICE   │                      │
│   │            │     │            │     │            │                      │
│   │ Update     │     │ Compare    │     │ Analyze    │                      │
│   │ Observed   │     │ Expected   │     │ Nuance     │                      │
│   └────────────┘     │ vs Actual  │     └────────────┘                      │
│                      └─────┬──────┘                                         │
│                            │                                                 │
│                            │ DetectedDelta                                  │
│                            ▼                                                 │
│                      ┌────────────┐     ┌────────────┐                      │
│                      │    UI      │────▶│  FEEDBACK  │                      │
│                      │  DISPLAY   │     │  MANAGER   │                      │
│                      │            │     │            │                      │
│                      │ Show Alert │     │ Haptic +   │                      │
│                      │ Cards      │     │ Sound      │                      │
│                      └────────────┘     └────────────┘                      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## DEVELOPMENT PHASES

### Phase 1: Core Recording (Weeks 1-2)
- [ ] Audio Capture Module
- [ ] Transcription Module (Apple Speech only)
- [ ] Basic UI (record/stop, show transcript)
- **Deliverable**: App that records and transcribes

### Phase 2: Context System (Weeks 3-4)
- [ ] Context Manager Module
- [ ] Built-in Domain Configs (3 templates)
- [ ] Session Setup UI
- **Deliverable**: User can select domain and set expectations

### Phase 3: Delta Detection (Weeks 5-7)
- [ ] Delta Detection Engine (rule-based first)
- [ ] Basic topic absence detection
- [ ] Basic speaker silence detection
- [ ] Delta Alert UI
- **Deliverable**: App detects and shows basic deltas

### Phase 4: LLM Integration (Weeks 8-10)
- [ ] LLM Service Module
- [ ] Backend API (proxy + session storage)
- [ ] Advanced detection (question dodge, tone shift)
- **Deliverable**: Full delta detection with LLM enhancement

### Phase 5: Polish (Weeks 11-12)
- [ ] Haptic/audio feedback
- [ ] Persistence Module
- [ ] Settings UI
- [ ] App Store prep
- **Deliverable**: App Store ready MVP

---

## COST ESTIMATES

### Development Costs (Contracting Out)

| Module | Complexity | Est. Hours | Est. Cost |
|--------|------------|------------|-----------|
| Audio Capture | Medium | 40 | $4,000 |
| Transcription | Medium | 60 | $6,000 |
| Context Manager | Medium | 50 | $5,000 |
| Delta Detection | High | 100 | $15,000 |
| LLM Service | Medium | 40 | $4,000 |
| UI/Display | High | 80 | $8,000 |
| Backend API | Medium | 60 | $6,000 |
| Persistence | Low | 20 | $2,000 |
| Integration/QA | High | 80 | $8,000 |
| **TOTAL** | | **530** | **~$58,000** |

*Assumes $100/hr average contractor rate*

### Operating Costs (Per Month)

| Service | Est. Cost |
|---------|-----------|
| LLM API (Claude/GPT-4) | $0.10-0.50 per session |
| Backend hosting | $50-200 |
| Apple Developer | $99/year |
| **Per 1000 users** | ~$200-500/month |

---

## SECURITY CONSIDERATIONS

| Risk | Mitigation |
|------|------------|
| Recording without consent | Clear UI indicator, mandatory consent screen |
| Audio data privacy | Process on-device when possible, delete after session |
| LLM API keys exposed | Never in client, always through backend proxy |
| Session data breach | Encrypt at rest, user-controlled deletion |
| Unauthorized recording | iOS permission system, audit logging |

---

## WHAT EACH DEVELOPER SEES

| Developer | Modules They Build | What They Know |
|-----------|-------------------|----------------|
| Dev A | Audio Capture | "Capture and buffer audio" |
| Dev B | Transcription | "Convert audio to text with timestamps" |
| Dev C | Context Manager | "Store session state and configs" |
| Dev D | UI/Display | "Show cards and status from ViewModel" |
| Dev E | Backend API | "Proxy requests, store sessions" |
| **You** | Delta Detection + LLM Integration | The actual innovation |

**Nobody but you sees how the pieces combine to detect what's NOT being said.**

---

## NEXT STEPS

1. **Validate MVP scope** - Is this the right feature set?
2. **Choose tech stack** - SwiftUI vs UIKit, backend language
3. **Spec out Delta Detection** - This is the IP, needs deep design
4. **Find/vet developers** - For the modular pieces
5. **Build Phase 1** - Get recording working first
