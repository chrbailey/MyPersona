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


def test_audit_trail():
    d = _tmp_dir()
    audit = AuditTrail(d)
    audit.log("test_action", "target_1", {"key": "val"}, "allowed")
    audit.log("test_action_2", "target_2", {}, "blocked")

    entries = audit.read()
    assert len(entries) == 2
    assert entries[0]["action"] == "test_action"
