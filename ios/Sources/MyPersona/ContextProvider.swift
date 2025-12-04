// MyPersona: Context Provider for LLM Integration
// Bridges real-time adaptive learning to any LLM
// Works with Claude, GPT, or any model via MCP or direct injection

import Foundation
import HealthKit
import CoreLocation

// MARK: - Context Provider

public class ContextProvider {

    // MARK: - Components

    private let behaviorDetector: MicroBehaviorDetector
    private let healthStore: HKHealthStore
    private let locationManager: CLLocationManager

    // MARK: - VA Schedule Awareness

    private var vaSchedule: VASchedule?

    // MARK: - Learned Patterns

    private var learnedPatterns: LearnedPatterns

    // MARK: - Avoid Triggers (Trauma Tier - Permanent)

    private var avoidTriggers: Set<String> = []

    // MARK: - Initialization

    public init() {
        self.behaviorDetector = MicroBehaviorDetector()
        self.healthStore = HKHealthStore()
        self.locationManager = CLLocationManager()
        self.learnedPatterns = LearnedPatterns()

        loadPersistedMemory()
        setupHealthKitObservers()
    }

    // MARK: - Context Generation

    /// Generate the full context block for LLM injection
    public func generateContextBlock() -> String {
        let context = behaviorDetector.currentContext
        let now = Date()
        let calendar = Calendar.current

        var block = "[CONTEXT]\n"

        // Time and schedule
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE h:mma"
        block += "Time: \(formatter.string(from: now))\n"

        // VA schedule status if known
        if let schedule = vaSchedule {
            if schedule.isInPrescribedRest(at: now) {
                block += "Schedule: Prescribed rest period\n"
            } else if let nextAppt = schedule.nextAppointment, nextAppt.timeIntervalSinceNow < 3600 {
                block += "Calendar: VA appointment in \(Int(nextAppt.timeIntervalSinceNow / 60)) minutes\n"
            }
        }

        // Real-time state
        if context.stressLevel > 0.6 {
            block += "Biometric: Elevated stress indicators\n"
        } else if context.stressLevel < 0.3 {
            block += "Biometric: Calm\n"
        }

        if context.cognitiveLoad > 0.5 {
            block += "State: Cognitive load elevated\n"
        }

        if context.frustrationLevel > 0.4 {
            block += "Pattern: Frustration detected\n"
        }

        if context.fatigueLevel > 0.5 {
            block += "State: Fatigue indicators\n"
        }

        // Social context
        switch context.socialContext {
        case .alone:
            block += "Social: Alone\n"
        case .withKnown:
            block += "Social: With familiar people\n"
        case .withUnknown:
            block += "Social: Others present\n"
        }

        // Location/motion
        if context.isInTransit {
            block += "Motion: In transit\n"
        }

        // Learned patterns
        if learnedPatterns.prefersBrief {
            block += "Preference: Brief responses\n"
        }

        if learnedPatterns.morningAnxiety > 0.5 && calendar.component(.hour, from: now) < 10 {
            block += "Pattern: Morning typically elevated\n"
        }

        // Recommended response style
        block += "\n[RESPONSE GUIDANCE]\n"
        block += "Length: \(responseGuidance())\n"

        if context.overwhelmLevel > 0.6 {
            block += "Simplify: Maximum\n"
        }

        if avoidTriggers.count > 0 {
            block += "Avoid: \(avoidTriggers.joined(separator: ", "))\n"
        }

        return block
    }

    /// Get response style recommendation
    private func responseGuidance() -> String {
        let context = behaviorDetector.currentContext

        if context.overwhelmLevel > 0.7 || context.cognitiveLoad > 0.8 {
            return "One word if possible"
        } else if context.frustrationLevel > 0.5 || context.stressLevel > 0.7 {
            return "One sentence maximum"
        } else if context.preferredResponseLength == .brief {
            return "Brief"
        } else {
            return "Normal"
        }
    }

    // MARK: - Signal Input

    /// Feed a raw signal into the system
    public func ingest(_ signal: MicroSignal) {
        behaviorDetector.process(signal)
        updateLearnedPatterns()
    }

    /// Update learned patterns based on accumulated behavior
    private func updateLearnedPatterns() {
        let context = behaviorDetector.currentContext

        // Learn preference for brief responses
        if context.preferredResponseLength == .brief || context.preferredResponseLength == .minimal {
            learnedPatterns.prefersBrief = true
        }

        // Persist periodically
        savePersistedMemory()
    }

    // MARK: - VA Schedule Integration

    public func setVASchedule(_ schedule: VASchedule) {
        self.vaSchedule = schedule
    }

    // MARK: - Trauma Triggers

    /// Mark something as a permanent avoid trigger
    public func markAsTrauma(_ trigger: String) {
        avoidTriggers.insert(trigger)
        savePersistedMemory()
    }

    // MARK: - Quiet Mode

    /// Check if the system should NOT respond
    public func shouldBeQuiet() -> Bool {
        let context = behaviorDetector.currentContext
        let now = Date()

        // Prescribed rest periods
        if let schedule = vaSchedule, schedule.isInPrescribedRest(at: now) {
            return true
        }

        // Deep calm state (don't interrupt)
        if context.stressLevel < 0.2 && context.engagementLevel < 0.3 {
            return true
        }

        // Overwhelmed (reduce all input)
        if context.overwhelmLevel > 0.9 {
            return true
        }

        return false
    }

    // MARK: - Persistence

    private func savePersistedMemory() {
        // Save to UserDefaults or secure storage
        let data: [String: Any] = [
            "avoidTriggers": Array(avoidTriggers),
            "prefersBrief": learnedPatterns.prefersBrief,
            "morningAnxiety": learnedPatterns.morningAnxiety
        ]

        if let encoded = try? JSONSerialization.data(withJSONObject: data) {
            UserDefaults.standard.set(encoded, forKey: "mypersona_memory")
        }
    }

    private func loadPersistedMemory() {
        guard let data = UserDefaults.standard.data(forKey: "mypersona_memory"),
              let decoded = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return
        }

        if let triggers = decoded["avoidTriggers"] as? [String] {
            avoidTriggers = Set(triggers)
        }
        if let brief = decoded["prefersBrief"] as? Bool {
            learnedPatterns.prefersBrief = brief
        }
        if let morning = decoded["morningAnxiety"] as? Double {
            learnedPatterns.morningAnxiety = morning
        }
    }

    // MARK: - HealthKit Integration

    private func setupHealthKitObservers() {
        guard HKHealthStore.isHealthDataAvailable() else { return }

        let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate)!

        let query = HKObserverQuery(sampleType: heartRateType, predicate: nil) { [weak self] _, completionHandler, error in
            if error == nil {
                self?.fetchLatestHeartRate()
            }
            completionHandler()
        }

        healthStore.execute(query)
    }

    private func fetchLatestHeartRate() {
        let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate)!
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)

        let query = HKSampleQuery(sampleType: heartRateType, predicate: nil, limit: 1, sortDescriptors: [sortDescriptor]) { [weak self] _, samples, _ in
            guard let sample = samples?.first as? HKQuantitySample else { return }

            let bpm = sample.quantity.doubleValue(for: HKUnit(from: "count/min"))
            self?.ingest(.heartRate(bpm: bpm, hrv: nil))
        }

        healthStore.execute(query)
    }
}

// MARK: - Supporting Types

public struct VASchedule {
    let sleepStart: DateComponents  // e.g., 10pm
    let sleepEnd: DateComponents    // e.g., 6am
    let restPeriods: [DateInterval]
    let appointments: [Date]

    var nextAppointment: Date? {
        appointments.first { $0 > Date() }
    }

    func isInPrescribedRest(at date: Date) -> Bool {
        let calendar = Calendar.current
        let hour = calendar.component(.hour, from: date)

        // Sleep window check
        let sleepStartHour = sleepStart.hour ?? 22
        let sleepEndHour = sleepEnd.hour ?? 6

        if sleepStartHour > sleepEndHour {
            // Overnight (e.g., 10pm - 6am)
            if hour >= sleepStartHour || hour < sleepEndHour {
                return true
            }
        } else {
            // Same day window
            if hour >= sleepStartHour && hour < sleepEndHour {
                return true
            }
        }

        // Check rest periods
        return restPeriods.contains { $0.contains(date) }
    }
}

public struct LearnedPatterns {
    var prefersBrief: Bool = false
    var morningAnxiety: Double = 0.0
    var vaAppointmentStress: Double = 0.0
    var typingDifficulty: Double = 0.0
    var crowdedSpaceAnxiety: Double = 0.0
}

// MARK: - LLM Integration Extension

extension ContextProvider {

    /// Format for Claude MCP tool
    public func asMCPResource() -> [String: Any] {
        return [
            "uri": "persona://context/current",
            "name": "Current User Context",
            "mimeType": "text/plain",
            "text": generateContextBlock()
        ]
    }

    /// Format for OpenAI function calling
    public func asOpenAIContext() -> [String: Any] {
        let context = behaviorDetector.currentContext
        return [
            "context": context.toDictionary(),
            "quiet_mode": shouldBeQuiet(),
            "avoid_triggers": Array(avoidTriggers),
            "response_guidance": responseGuidance()
        ]
    }

    /// Plain text for any system prompt
    public func asSystemPromptAddition() -> String {
        return """
        IMPORTANT USER CONTEXT (real-time, adaptive):

        \(generateContextBlock())

        CRITICAL: This context was inferred from real-time signals. Respond to what the user NEEDS, not just what they literally said. If quiet mode is indicated, consider whether a response is even necessary.
        """
    }
}
