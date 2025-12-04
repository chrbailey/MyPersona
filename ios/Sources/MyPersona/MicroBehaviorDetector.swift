// MyPersona: Real-Time Micro-Behavior Detector
// Piggybacks on iOS frameworks for TikTok-style signal detection
// All processing on-device. Nothing leaves. Ever.

import Foundation
import ARKit
import HealthKit
import CoreMotion

// MARK: - Signal Types

/// Raw signals from device sensors
public enum MicroSignal {
    case gazeDwell(duration: TimeInterval, target: String)
    case scrollSpeed(velocity: Double)
    case hesitation(duration: TimeInterval)
    case typing(keystrokes: Int, corrections: Int, duration: TimeInterval)
    case heartRate(bpm: Double, hrv: Double?)
    case appSwitch(from: String, to: String)
    case tapPattern(count: Int, interval: TimeInterval)
    case motionState(moving: Bool, speed: Double?)
    case proximity(peopleNearby: Int, isKnown: Bool)
}

/// Processed behavior interpretation
public struct BehaviorSignal {
    let type: BehaviorType
    let confidence: Double
    let weight: Double
    let timestamp: Date

    enum BehaviorType {
        case interest          // Dwelling, rereading
        case disinterest       // Quick scroll, dismiss
        case frustration       // Repeated taps, corrections
        case overwhelm         // Rapid switching, erratic behavior
        case cognitiveLoad     // High error rate, slow typing
        case calm              // Steady HR, slow movement
        case anxiety           // HR spike, stillness
        case fatigue           // Low HRV, slow response
        case socialAwareness   // Context shift when others present
    }
}

// MARK: - TikTok-Style Scoring

/// Weights based on TikTok algorithm research
/// Hesitation > explicit signals
public struct SignalWeights {
    // Positive signals (interest)
    static let gazeDwellOver2_3s: Double = 10.0    // TikTok's magic number
    static let completeRead: Double = 8.0
    static let reread: Double = 10.0
    static let slowScroll: Double = 4.0

    // Negative signals (weighted heavier per asymmetric learning)
    static let quickScroll: Double = -1.0
    static let rapidDismiss: Double = -3.0
    static let frustrationTap: Double = -5.0
    static let overwhelmSwitch: Double = -2.0

    // Veteran-specific (3x weight for negative)
    static let cognitiveStruggle: Double = -8.0    // TBI awareness
    static let typingDifficulty: Double = -6.0     // Physical limitation
    static let anxietySpike: Double = -10.0        // PTSD awareness
}

// MARK: - Micro-Behavior Detector

public class MicroBehaviorDetector: NSObject {

    // MARK: - Properties

    /// Asymmetric memory tiers
    private var traumaMemories: [String: Double] = [:]      // Never decay
    private var warningSignals: [String: SignalMemory] = [:] // Slow decay τ=30d
    private var baselinePatterns: [String: SignalMemory] = [:] // Fast decay τ=7d

    /// Recent behavior window for pattern detection
    private var recentSignals: [MicroSignal] = []
    private let signalWindowDuration: TimeInterval = 60.0 // 1 minute window

    /// Current context vector (real-time)
    public private(set) var currentContext: ContextVector

    /// Hesitation detector state
    private var gazeStartTime: Date?
    private var lastGazeTarget: String?

    /// App switch detector
    private var recentAppSwitches: [(Date, String, String)] = []

    // MARK: - Initialization

    public override init() {
        self.currentContext = ContextVector()
        super.init()
    }

    // MARK: - Signal Processing

    /// Process a raw signal and update context
    public func process(_ signal: MicroSignal) {
        // Add to recent window
        recentSignals.append(signal)
        cleanOldSignals()

        // Convert to behavior signals
        let behaviors = interpretSignal(signal)

        // Update context vector
        for behavior in behaviors {
            updateContext(with: behavior)
            updateMemory(with: behavior)
        }
    }

    /// Interpret raw signal into behavior
    private func interpretSignal(_ signal: MicroSignal) -> [BehaviorSignal] {
        var behaviors: [BehaviorSignal] = []
        let now = Date()

        switch signal {

        // GAZE DWELL - TikTok's secret sauce
        case .gazeDwell(let duration, let target):
            if duration > 2.3 {
                // The magic 2.3 second threshold
                behaviors.append(BehaviorSignal(
                    type: .interest,
                    confidence: min(duration / 5.0, 1.0),
                    weight: SignalWeights.gazeDwellOver2_3s,
                    timestamp: now
                ))
            } else if duration < 0.5 {
                behaviors.append(BehaviorSignal(
                    type: .disinterest,
                    confidence: 0.7,
                    weight: SignalWeights.quickScroll,
                    timestamp: now
                ))
            }

            // Reread detection
            if target == lastGazeTarget {
                behaviors.append(BehaviorSignal(
                    type: .interest,
                    confidence: 0.9,
                    weight: SignalWeights.reread,
                    timestamp: now
                ))
            }
            lastGazeTarget = target

        // SCROLL SPEED
        case .scrollSpeed(let velocity):
            if velocity > 2000 { // pixels per second, fast scroll
                behaviors.append(BehaviorSignal(
                    type: .disinterest,
                    confidence: 0.8,
                    weight: SignalWeights.rapidDismiss,
                    timestamp: now
                ))
            } else if velocity < 200 { // slow, deliberate scroll
                behaviors.append(BehaviorSignal(
                    type: .interest,
                    confidence: 0.6,
                    weight: SignalWeights.slowScroll,
                    timestamp: now
                ))
            }

        // HESITATION - pause before action
        case .hesitation(let duration):
            if duration > 1.5 {
                behaviors.append(BehaviorSignal(
                    type: .interest,
                    confidence: min(duration / 4.0, 1.0),
                    weight: duration > 2.3 ? SignalWeights.gazeDwellOver2_3s : 5.0,
                    timestamp: now
                ))
            }

        // TYPING - cognitive load and physical limitation detection
        case .typing(let keystrokes, let corrections, let duration):
            let errorRate = Double(corrections) / Double(max(keystrokes, 1))
            let typingSpeed = Double(keystrokes) / duration

            if errorRate > 0.3 {
                // High error rate - cognitive load or physical difficulty
                behaviors.append(BehaviorSignal(
                    type: .cognitiveLoad,
                    confidence: min(errorRate, 1.0),
                    weight: SignalWeights.cognitiveStruggle,
                    timestamp: now
                ))
            }

            if typingSpeed < 1.0 && errorRate > 0.2 {
                // Slow with errors - likely physical limitation
                behaviors.append(BehaviorSignal(
                    type: .frustration,
                    confidence: 0.8,
                    weight: SignalWeights.typingDifficulty,
                    timestamp: now
                ))
            }

        // HEART RATE - anxiety/calm detection
        case .heartRate(let bpm, let hrv):
            // Check for spike (relative to baseline)
            let baseline = baselinePatterns["resting_hr"]?.value ?? 70.0
            let deviation = (bpm - baseline) / baseline

            if deviation > 0.3 { // 30% above baseline
                behaviors.append(BehaviorSignal(
                    type: .anxiety,
                    confidence: min(deviation, 1.0),
                    weight: SignalWeights.anxietySpike,
                    timestamp: now
                ))
            } else if deviation < 0.1 && (hrv ?? 0) > 50 {
                behaviors.append(BehaviorSignal(
                    type: .calm,
                    confidence: 0.7,
                    weight: 3.0,
                    timestamp: now
                ))
            }

        // APP SWITCHING - overwhelm detection
        case .appSwitch(let from, let to):
            recentAppSwitches.append((now, from, to))
            recentAppSwitches = recentAppSwitches.filter {
                now.timeIntervalSince($0.0) < 60
            }

            if recentAppSwitches.count > 5 {
                // More than 5 switches in a minute = overwhelm
                behaviors.append(BehaviorSignal(
                    type: .overwhelm,
                    confidence: Double(recentAppSwitches.count) / 10.0,
                    weight: SignalWeights.overwhelmSwitch * Double(recentAppSwitches.count),
                    timestamp: now
                ))
            }

        // TAP PATTERN - frustration detection
        case .tapPattern(let count, let interval):
            if count > 3 && interval < 0.3 {
                // Rapid repeated taps = frustration
                behaviors.append(BehaviorSignal(
                    type: .frustration,
                    confidence: 0.9,
                    weight: SignalWeights.frustrationTap,
                    timestamp: now
                ))
            }

        // MOTION - context awareness
        case .motionState(let moving, let speed):
            if moving, let s = speed, s > 1.0 {
                currentContext.isInTransit = true
            } else {
                currentContext.isInTransit = false
            }

        // PROXIMITY - social context
        case .proximity(let count, let isKnown):
            if count > 0 {
                behaviors.append(BehaviorSignal(
                    type: .socialAwareness,
                    confidence: 0.8,
                    weight: isKnown ? 2.0 : 5.0,
                    timestamp: now
                ))
            }
            currentContext.socialContext = count > 0 ? (isKnown ? .withKnown : .withUnknown) : .alone
        }

        return behaviors
    }

    // MARK: - Context Update

    /// Update the real-time context vector
    private func updateContext(with behavior: BehaviorSignal) {
        switch behavior.type {
        case .interest:
            currentContext.engagementLevel += 0.1 * behavior.confidence
        case .disinterest:
            currentContext.engagementLevel -= 0.1 * behavior.confidence
        case .frustration:
            currentContext.frustrationLevel += 0.2 * behavior.confidence
        case .overwhelm:
            currentContext.overwhelmLevel += 0.3 * behavior.confidence
            currentContext.preferredResponseLength = .minimal
        case .cognitiveLoad:
            currentContext.cognitiveLoad += 0.2 * behavior.confidence
            currentContext.preferredResponseLength = .brief
        case .calm:
            currentContext.stressLevel -= 0.1 * behavior.confidence
        case .anxiety:
            currentContext.stressLevel += 0.2 * behavior.confidence
        case .fatigue:
            currentContext.fatigueLevel += 0.15 * behavior.confidence
        case .socialAwareness:
            currentContext.isContextSensitive = true
        }

        // Clamp values to 0-1
        currentContext.normalize()
    }

    // MARK: - Asymmetric Memory

    private func updateMemory(with behavior: BehaviorSignal) {
        let key = "\(behavior.type)"

        // Determine tier based on severity
        if behavior.weight < -8 {
            // TRAUMA TIER - never decays
            traumaMemories[key] = max(traumaMemories[key] ?? 0, behavior.confidence)
        } else if behavior.weight < 0 {
            // WARNING TIER - slow decay, 3x weight for negative
            let alpha: Double = 0.3 // Faster learning for warnings
            let current = warningSignals[key]?.value ?? 0
            let newValue = (1 - alpha) * current + alpha * behavior.confidence
            warningSignals[key] = SignalMemory(value: newValue, lastUpdated: Date(), decayDays: 30)
        } else {
            // BASELINE TIER - fast decay
            let alpha: Double = 0.1
            let current = baselinePatterns[key]?.value ?? 0
            let newValue = (1 - alpha) * current + alpha * behavior.confidence
            baselinePatterns[key] = SignalMemory(value: newValue, lastUpdated: Date(), decayDays: 7)
        }
    }

    // MARK: - Memory Decay

    /// Apply time-based decay to memories (call periodically)
    public func applyDecay() {
        let now = Date()

        // Trauma never decays

        // Warning tier - slow decay
        for (key, memory) in warningSignals {
            let daysSince = now.timeIntervalSince(memory.lastUpdated) / 86400
            let decayFactor = exp(-daysSince / Double(memory.decayDays))
            warningSignals[key]?.value *= decayFactor
        }

        // Baseline tier - fast decay
        for (key, memory) in baselinePatterns {
            let daysSince = now.timeIntervalSince(memory.lastUpdated) / 86400
            let decayFactor = exp(-daysSince / Double(memory.decayDays))
            baselinePatterns[key]?.value *= decayFactor
        }

        // Clean up near-zero values
        warningSignals = warningSignals.filter { $0.value.value > 0.01 }
        baselinePatterns = baselinePatterns.filter { $0.value.value > 0.01 }
    }

    // MARK: - Helpers

    private func cleanOldSignals() {
        let cutoff = Date().addingTimeInterval(-signalWindowDuration)
        recentSignals = recentSignals.filter { _ in true } // Would filter by timestamp if stored
    }
}

// MARK: - Supporting Types

struct SignalMemory {
    var value: Double
    var lastUpdated: Date
    var decayDays: Int
}

public struct ContextVector {
    // Real-time state
    public var stressLevel: Double = 0.0
    public var engagementLevel: Double = 0.5
    public var frustrationLevel: Double = 0.0
    public var overwhelmLevel: Double = 0.0
    public var cognitiveLoad: Double = 0.0
    public var fatigueLevel: Double = 0.0

    // Context flags
    public var isInTransit: Bool = false
    public var isContextSensitive: Bool = false
    public var socialContext: SocialContext = .alone

    // Preferences (learned)
    public var preferredResponseLength: ResponseLength = .normal

    public enum SocialContext {
        case alone
        case withKnown
        case withUnknown
    }

    public enum ResponseLength {
        case minimal  // One word if possible
        case brief    // One sentence
        case normal   // Standard response
        case detailed // Full explanation
    }

    mutating func normalize() {
        stressLevel = max(0, min(1, stressLevel))
        engagementLevel = max(0, min(1, engagementLevel))
        frustrationLevel = max(0, min(1, frustrationLevel))
        overwhelmLevel = max(0, min(1, overwhelmLevel))
        cognitiveLoad = max(0, min(1, cognitiveLoad))
        fatigueLevel = max(0, min(1, fatigueLevel))
    }

    /// Convert to dictionary for LLM context injection
    public func toDictionary() -> [String: Any] {
        return [
            "stress_level": stressLevel,
            "engagement": engagementLevel,
            "frustration": frustrationLevel,
            "overwhelm": overwhelmLevel,
            "cognitive_load": cognitiveLoad,
            "fatigue": fatigueLevel,
            "in_transit": isInTransit,
            "context_sensitive": isContextSensitive,
            "social": "\(socialContext)",
            "preferred_length": "\(preferredResponseLength)"
        ]
    }
}

// MARK: - ARKit Extension for Gaze Tracking

extension MicroBehaviorDetector: ARSessionDelegate {

    public func session(_ session: ARSession, didUpdate anchors: [ARAnchor]) {
        for anchor in anchors {
            guard let faceAnchor = anchor as? ARFaceAnchor else { continue }

            // Get gaze point in 3D space
            let lookAtPoint = faceAnchor.lookAtPoint

            // Convert to screen coordinates and track dwell time
            // (Simplified - actual implementation needs camera transform)
            let gazeTarget = "screen_region_\(Int(lookAtPoint.x * 10))_\(Int(lookAtPoint.y * 10))"

            if gazeTarget == lastGazeTarget {
                // Still looking at same region - accumulate dwell
                if let start = gazeStartTime {
                    let duration = Date().timeIntervalSince(start)
                    if duration > 0.5 { // Minimum meaningful dwell
                        process(.gazeDwell(duration: duration, target: gazeTarget))
                    }
                }
            } else {
                // Gaze shifted - reset timer
                gazeStartTime = Date()
            }

            lastGazeTarget = gazeTarget
        }
    }
}
