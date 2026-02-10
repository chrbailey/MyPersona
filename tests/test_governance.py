"""Tests for governance layer."""

import tempfile
from pathlib import Path

from src.models import EmotionalMemory, HoldRequest
from src.memory import GovernanceLayer, should_promote, promote, can_delete, AuditTrail


def _tmp_dir():
    d = Path(tempfile.mkdtemp())
    return d


def test_governance_allow_unverified_write():
    gov = GovernanceLayer(_tmp_dir())
    mem = EmotionalMemory(content="test", trust_zone="unverified")
    result = gov.gate_memory_write(mem)
    assert result == "allowed"


def test_governance_hold_delete_promoted():
    gov = GovernanceLayer(_tmp_dir())
    mem = EmotionalMemory(content="test", trust_zone="promoted")
    result = gov.gate_memory_delete(mem)
    assert result == "held"
    assert len(gov.pending_holds()) == 1


def test_governance_resolve_hold():
    gov = GovernanceLayer(_tmp_dir())
    mem = EmotionalMemory(content="test", trust_zone="promoted")
    gov.gate_memory_delete(mem)

    holds = gov.pending_holds()
    assert len(holds) == 1

    resolved = gov.resolve_hold(holds[0].hold_id, "reject", "keep it")
    assert resolved is not None
    assert resolved.status == "rejected"
    assert len(gov.pending_holds()) == 0


def test_trust_zone_promotion():
    mem = EmotionalMemory(content="test", corroboration_count=3)
    assert should_promote(mem)
    promote(mem)
    assert mem.trust_zone == "promoted"


def test_trust_zone_no_premature_promotion():
    mem = EmotionalMemory(content="test", corroboration_count=1)
    assert not should_promote(mem)


def test_can_delete_unverified():
    mem = EmotionalMemory(content="test", trust_zone="unverified")
    assert can_delete(mem)


def test_cannot_delete_promoted():
    mem = EmotionalMemory(content="test", trust_zone="promoted")
    assert not can_delete(mem)


def test_governance_hold_high_encoding_weight():
    """High encoding weight memories should be held for review."""
    gov = GovernanceLayer(_tmp_dir())
    mem = EmotionalMemory(content="My mother just passed away", trust_zone="unverified",
                          encoding_weight=1.5)  # above 1.3 threshold
    result = gov.gate_memory_write(mem)
    assert result == "held"
    assert len(gov.pending_holds()) == 1
    assert "encoding weight" in gov.pending_holds()[0].reason.lower()


def test_governance_allow_normal_encoding_weight():
    """Normal encoding weight memories pass through."""
    gov = GovernanceLayer(_tmp_dir())
    mem = EmotionalMemory(content="Had a good meeting", trust_zone="unverified",
                          encoding_weight=0.6)
    result = gov.gate_memory_write(mem)
    assert result == "allowed"


def test_governance_hold_high_conflict():
    """High persona-reward conflict memories should be held."""
    gov = GovernanceLayer(_tmp_dir())
    mem = EmotionalMemory(content="I hate documentation but I should do it",
                          trust_zone="unverified", conflict_score=0.7)
    result = gov.gate_memory_write(mem)
    assert result == "held"
    assert "conflict" in gov.pending_holds()[0].reason.lower()


def test_emotional_decay_recent_memories():
    """Recent memories should have high retention regardless of weight."""
    from src.memory import emotional_decay
    assert emotional_decay(1.0, 0.5, 0.3) > 0.9
    assert emotional_decay(1.0, 1.5, 0.8) > 0.99


def test_emotional_decay_old_mundane():
    """30-day-old mundane memories should mostly fade."""
    from src.memory import emotional_decay
    retention = emotional_decay(720.0, 0.5, 0.2)
    assert retention < 0.3


def test_emotional_decay_old_flashbulb():
    """30-day-old flashbulb memories should persist strongly."""
    from src.memory import emotional_decay
    retention = emotional_decay(720.0, 1.5, 1.0)
    assert retention > 0.5


def test_emotional_decay_ordering():
    """Higher encoding weight = slower decay at same age."""
    from src.memory import emotional_decay
    low = emotional_decay(168.0, 0.3, 0.2)   # 1 week, mundane
    high = emotional_decay(168.0, 1.5, 0.8)   # 1 week, flashbulb
    assert high > low


def test_audit_trail():
    d = _tmp_dir()
    audit = AuditTrail(d)
    audit.log("test_action", "target_1", {"key": "val"}, "allowed")
    audit.log("test_action_2", "target_2", {}, "blocked")

    entries = audit.read()
    assert len(entries) == 2
    assert entries[0]["action"] == "test_action"
