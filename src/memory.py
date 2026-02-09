"""
Memory layer: Pinecone store, emotional timeline, governance (holds, trust zones, audit).
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .models import MoodState, EmotionalMemory, HoldRequest


# =============================================================================
# MEMORY STORE (Pinecone)
# =============================================================================

class MemoryStore:
    def __init__(self, index_name: str = None, namespace: str = "memories"):
        self.index_name = index_name or os.getenv("PINECONE_INDEX", "marine-agent-ahgen")
        self.namespace = namespace
        self._index = None

    @property
    def index(self):
        if self._index is None:
            from pinecone import Pinecone
            pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
            self._index = pc.Index(self.index_name)
        return self._index

    def store(self, memory: EmotionalMemory) -> dict:
        record = memory.to_pinecone_record()
        self.index.upsert_records(self.namespace, [record])
        return record

    def search(self, query: str, limit: int = 5, filter_dict: Optional[dict] = None) -> List[dict]:
        kwargs = {"namespace": self.namespace,
                  "query": {"top_k": limit, "inputs": {"text": query}}}
        if filter_dict:
            kwargs["query"]["filter"] = filter_dict
        results = self.index.search(**kwargs)
        return [match for match in results.get("result", {}).get("hits", [])]

    def get(self, memory_id: str) -> Optional[dict]:
        try:
            result = self.index.fetch(ids=[memory_id], namespace=self.namespace)
            return result.get("vectors", {}).get(memory_id)
        except Exception:
            return None

    def delete(self, memory_id: str):
        self.index.delete(ids=[memory_id], namespace=self.namespace)


# =============================================================================
# TIMELINE MANAGER
# =============================================================================

class TimelineManager:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "mood_timeline.json"
        self.timeline: Dict[str, List[dict]] = {}
        self._load()

    def record(self, mood: MoodState, topics: List[str], session_id: str = ""):
        entry = {
            "valence": round(mood.valence, 3), "arousal": round(mood.arousal, 3),
            "quadrant": mood.quadrant.value, "intensity": round(mood.intensity, 3),
            "confidence": round(mood.confidence, 3), "session_id": session_id,
            "timestamp": mood.timestamp.isoformat(),
        }
        for topic in topics:
            if topic not in self.timeline:
                self.timeline[topic] = []
            self.timeline[topic].append(entry)

        if "_global" not in self.timeline:
            self.timeline["_global"] = []
        self.timeline["_global"].append(entry)
        self._save()

    def get_timeline(self, topic: Optional[str] = None, days_back: int = 30) -> List[dict]:
        key = topic or "_global"
        entries = self.timeline.get(key, [])
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        return [e for e in entries if e.get("timestamp", "") >= cutoff]

    def get_trend(self, topic: Optional[str] = None, window: int = 5) -> dict:
        entries = self.get_timeline(topic)
        if len(entries) < 2:
            return {"trend": "insufficient_data", "entries": len(entries)}

        recent = entries[-window:] if len(entries) >= window else entries
        valences = [e["valence"] for e in recent]
        avg_valence = sum(valences) / len(valences)

        if len(valences) >= 2:
            first_half = valences[:len(valences)//2]
            second_half = valences[len(valences)//2:]
            diff = sum(second_half) / len(second_half) - sum(first_half) / len(first_half)
            if diff > 0.1:
                trend = "improving"
            elif diff < -0.1:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "trend": trend, "avg_valence": round(avg_valence, 3),
            "entries": len(entries),
            "recent_quadrants": [e["quadrant"] for e in recent],
        }

    def get_all_topics(self) -> List[str]:
        return [k for k in self.timeline.keys() if k != "_global"]

    def _save(self):
        self.path.write_text(json.dumps(self.timeline, indent=2))

    def _load(self):
        if not self.path.exists():
            return
        try:
            self.timeline = json.loads(self.path.read_text())
        except Exception:
            self.timeline = {}


# =============================================================================
# TRUST ZONES
# =============================================================================

def should_promote(memory: EmotionalMemory, threshold: int = 3) -> bool:
    return memory.corroboration_count >= threshold and memory.trust_zone == "unverified"


def promote(memory: EmotionalMemory):
    memory.trust_zone = "promoted"


def can_delete(memory: EmotionalMemory) -> bool:
    return memory.trust_zone != "promoted"


# =============================================================================
# GOVERNANCE LAYER
# =============================================================================

class GovernanceLayer:
    PROMOTION_THRESHOLD = 3
    CONFIDENCE_THRESHOLD = 0.7

    def __init__(self, data_dir: Path):
        self.holds_path = data_dir / "holds.json"
        self.audit_path = data_dir / "audit_log.jsonl"
        self.holds: List[HoldRequest] = []
        self._load_holds()

    def gate_memory_write(self, memory: EmotionalMemory) -> str:
        if memory.trust_zone == "unverified":
            self._audit("memory_write", memory.memory_id, {"zone": "unverified"}, "allowed")
            return "allowed"
        if memory.corroboration_count >= self.PROMOTION_THRESHOLD:
            self._audit("memory_promote", memory.memory_id,
                        {"corroboration": memory.corroboration_count}, "allowed")
            return "allowed"

        hold = HoldRequest(action="promote_memory", target_id=memory.memory_id,
                           reason=f"Corroboration {memory.corroboration_count}/{self.PROMOTION_THRESHOLD}")
        self.holds.append(hold)
        self._save_holds()
        self._audit("hold_created", hold.hold_id, {"target": memory.memory_id}, "held")
        return "held"

    def gate_memory_delete(self, memory: EmotionalMemory) -> str:
        if memory.trust_zone == "promoted":
            hold = HoldRequest(action="delete_memory", target_id=memory.memory_id,
                               reason="Deletion of promoted memory requires human approval")
            self.holds.append(hold)
            self._save_holds()
            self._audit("hold_created", hold.hold_id,
                        {"action": "delete", "target": memory.memory_id}, "held")
            return "held"
        return "allowed"

    def resolve_hold(self, hold_id: str, decision: str, reason: str = "") -> Optional[HoldRequest]:
        for hold in self.holds:
            if hold.hold_id == hold_id and hold.status == "pending":
                hold.status = "approved" if decision == "approve" else "rejected"
                hold.resolution_reason = reason
                hold.resolved_at = datetime.utcnow()
                self._save_holds()
                self._audit("hold_resolved", hold_id,
                            {"decision": decision, "reason": reason}, decision)
                return hold
        return None

    def pending_holds(self) -> List[HoldRequest]:
        return [h for h in self.holds if h.status == "pending"]

    def all_holds(self, include_resolved: bool = False) -> List[HoldRequest]:
        if include_resolved:
            return self.holds
        return self.pending_holds()

    def _audit(self, action: str, target_id: str, details: dict, outcome: str):
        with open(self.audit_path, "a") as f:
            f.write(json.dumps({
                "timestamp": datetime.utcnow().isoformat(),
                "action": action, "target_id": target_id,
                "details": details, "outcome": outcome,
            }) + "\n")

    def _save_holds(self):
        data = []
        for h in self.holds:
            data.append({
                "hold_id": h.hold_id, "action": h.action, "target_id": h.target_id,
                "reason": h.reason, "requested_at": h.requested_at.isoformat(),
                "status": h.status, "resolution_reason": h.resolution_reason,
                "resolved_at": h.resolved_at.isoformat() if h.resolved_at else None,
            })
        self.holds_path.write_text(json.dumps(data, indent=2))

    def _load_holds(self):
        if not self.holds_path.exists():
            return
        try:
            data = json.loads(self.holds_path.read_text())
            self.holds = []
            for d in data:
                self.holds.append(HoldRequest(
                    hold_id=d["hold_id"], action=d["action"], target_id=d["target_id"],
                    reason=d.get("reason", ""), status=d.get("status", "pending"),
                    resolution_reason=d.get("resolution_reason", ""),
                ))
        except Exception:
            self.holds = []


# =============================================================================
# AUDIT TRAIL
# =============================================================================

class AuditTrail:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "audit_log.jsonl"

    def log(self, action: str, target_id: str, details: dict, outcome: str):
        with open(self.path, "a") as f:
            f.write(json.dumps({
                "timestamp": datetime.utcnow().isoformat(),
                "action": action, "target_id": target_id,
                "details": details, "outcome": outcome,
            }) + "\n")

    def read(self, limit: int = 100) -> List[dict]:
        if not self.path.exists():
            return []
        entries = []
        for line in self.path.read_text().strip().split("\n"):
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries[-limit:]
