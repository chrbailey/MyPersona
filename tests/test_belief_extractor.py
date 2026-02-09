"""Tests for belief extractor (no API calls — test regex/heuristic paths only)."""

from src.engines import BeliefExtractor, AuthorityRef


def test_detect_institutional_authority():
    be = BeliefExtractor()
    refs = be.detect_authority_refs("My boss said we need to finish by Friday")
    assert len(refs) >= 1
    assert refs[0].tier == "institutional"


def test_detect_formal_authority():
    be = BeliefExtractor()
    refs = be.detect_authority_refs("The contract requires monthly reports")
    assert len(refs) >= 1
    assert refs[0].tier == "formal"


def test_detect_personal_authority():
    be = BeliefExtractor()
    refs = be.detect_authority_refs("My mentor suggested I focus on leadership")
    assert len(refs) >= 1
    assert refs[0].tier == "personal"


def test_detect_no_authority():
    be = BeliefExtractor()
    refs = be.detect_authority_refs("I went to the store today")
    assert len(refs) == 0


def test_extract_beliefs_simple():
    be = BeliefExtractor()
    beliefs = be.extract_beliefs_simple("I think the project will succeed. I'm sure we'll make it.")
    assert len(beliefs) >= 1


def test_extract_beliefs_simple_weak():
    be = BeliefExtractor()
    beliefs = be.extract_beliefs_simple("Maybe we should reconsider.")
    assert len(beliefs) >= 1
    assert beliefs[0].confidence == "weak"
