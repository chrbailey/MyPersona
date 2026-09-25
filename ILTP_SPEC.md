# Intermediary Lease Transaction Packet (ILTP)

## Core decision
Use a **Markdown wrapper with an embedded canonical YAML block** (`lease_packet.md`).

- Markdown stays human-readable for brokers, legal, and back office.
- YAML remains deterministic for validators, generators, and AI agents.
- The packet is the source of truth; Word, DocuSign, and PMS records are downstream artifacts.

## System role
The ILTP is the canonical, versioned transaction-state object connecting:

1. LOI intake/extraction
2. Lease document generation (DOCX/PDF)
3. DocuSign envelope creation and execution
4. Yardi/AppFolio payload generation/import
5. Audit + closeout evidence

## State machine

```yaml
state_machine:
  states:
    - loi_received
    - extraction_pending
    - packet_draft
    - validation_failed
    - backoffice_review
    - legal_review_required
    - ready_for_document_generation
    - lease_doc_generated
    - internal_approval_pending
    - ready_for_docusign
    - sent_for_signature
    - partially_executed
    - fully_executed
    - pms_payload_ready
    - pms_imported
    - closeout_complete
    - canceled
    - superseded
  terminal_states:
    - closeout_complete
    - canceled
    - superseded
```

## Canonical packet shape

```yaml
packet:
  packet_id: lease_2026_000142
  packet_type: commercial_small_bay_lease
  status: packet_draft
  version: 0.1.0
  created_at: 2026-05-13T12:00:00-07:00
  updated_at: 2026-05-13T12:00:00-07:00
source: {}
parties: {}
property: {}
premises: {}
deal_terms: {}
economics: {}
legal_terms: {}
brokerage: {}
document_generation: {}
docusign: {}
pms_mapping: {}
exceptions: {}
approvals: {}
artifacts: {}
audit_events: []
```

## Architectural invariants

1. Packet is canonical deal state; downstream outputs cannot drift.
2. No DocuSign send while blocker exceptions exist.
3. No PMS payload generation before signed lease artifact exists.
4. Tenant legal name must reconcile across packet, lease, DocuSign, and PMS payload.
5. Packet hash change marks generated artifacts stale.
6. Manual overrides must emit audit events.

## Validation tiers

- **Blockers**: required fields and preconditions for generation/sending/import.
- **Consistency**: date/order/math reconciliation checks.
- **Risk**: legal-review and approval trigger checks.

## Artifact strategy
Each generated artifact stores:

- source packet version/hash
- generated timestamp
- template/profile id
- artifact hash
- staleness status

## Mapping strategy
Use profile-driven PMS mappings rather than one hard-coded schema.

- `yardi_voyager_commercial_v1`
- `appfolio_commercial_v1`

Flow: `canonical packet fields -> mapping profile -> PMS-specific payload`.

## Agent model (Software 1.0 / 2.0 / 3.0)

- **Software 1.0**: deterministic validation + generation code.
- **Software 2.0**: extraction/classification/search over LOIs and packet evidence.
- **Software 3.0**: natural-language operator layer for exception analysis, drafting, and patch proposals.

Operating pattern:

- AI proposes
- Validator blocks
- Human approves
- Generator emits
- Audit records

## MVP implementation passes

1. Packet template (`lease_packet.md`)
2. Deterministic validator (`validate_packet.py`)
3. Lease generation (`generate_docx.py`)
4. DocuSign payload generation (`generate_docusign_payload.py`)
5. PMS export (`generate_pms_payload.py`)

## Recommended repository layout

```text
lease-packet-engine/
  packets/
  schemas/
  templates/
  mappings/
  artifacts/
  src/
  tests/
```

## Executive thesis
The ILTP is not a prettier lease draft. It is a bounded-context transaction compiler IR that preserves negotiated intent, normalizes it into validated fields, generates downstream artifacts without drift, and proves what happened during audit/closeout.
