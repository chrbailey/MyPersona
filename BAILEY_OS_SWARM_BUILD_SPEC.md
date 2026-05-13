# Bailey OS Swarm Build Specification

## 1) Product Definition

Bailey OS is a **local, evidence-first agent operating layer** that provides governed, repeatable workflows over repos, prompts, tools, skills, and memories.

It is **not**:
- a generic chatbot,
- an ungoverned autonomous coding swarm,
- a domain plugin bundle before core runtime guarantees exist.

Primary executable:
- `bailey`

Initial commands:
- `bailey init`
- `bailey status`
- `bailey scan`
- `bailey audit-repo`
- `bailey extract-claims`
- `bailey validate-claims`
- `bailey critic`
- `bailey ralph`
- `bailey report`
- `bailey run`

Core doctrine:
1. Deterministic first, LLM second.
2. No factual claim ships without evidence or explicit inference label.
3. Every run produces logs.
4. Every module has a contract.
5. Every feature has tests.
6. Every packet has acceptance criteria.
7. Ralph routes every artifact decision.
8. PromptSpeak governs workflows only where parser/schema/runtime exist.
9. Plugins require explicit permission boundaries and must not mutate global state implicitly.
10. ERP/NetSuite/SAP plugins are out of scope until the spine is complete.

---

## 2) System Architecture

Reference repository shape:

```text
bailey-os/
  README.md
  BAILEY_OS_SPEC.md
  BAILEY_OS_SWARM_BUILD_SPEC.md
  ARCHITECTURE.md
  MODULE_CONTRACTS.md
  BUILD_ORDER.md
  TRACEABILITY_MATRIX.md
  pyproject.toml
  bailey_os/
    cli/
    core/
    context/
    promptspeak/
    skills/
    plugins/
    tools/
    evidence/
    claims/
    critic/
    ralph/
    memory/
    runs/
    reporter/
    security/
    integrations/
  docs/
    product/
    architecture/
    business_process/
    functional_specs/
    technical_specs/
    design_docs/
    agent_packets/
    test_plans/
    decisions/
  tests/
    unit/
    integration/
    functional/
    golden/
    fixtures/
  scripts/
    dev/
    build/
    test/
    validate/
    generate_packets/
  agent_packets/
    000-control/
    001-cli/
    ...
```

Architectural backbone:
- **CLI runtime**: command surface, config, and run orchestration.
- **Context system**: project model, config/model loading, file inventory, budgeted summarization.
- **Claim/evidence subsystem**: atomic claims, proof references, integrity checks.
- **Critic loop**: deterministic and model-assisted validation.
- **Ralph router**: decision state machine controlling promotion/revision/hold.
- **Reporter**: standardized outputs with evidence map and decision trace.
- **Extension surface**: PromptSpeak, skills, plugins, tools.

---

## 3) Module Boundaries

### Core boundaries
- `bailey_os/cli`: user-facing commands only; no deep business logic.
- `bailey_os/context`: project discovery, policy loading, and context packaging.
- `bailey_os/claims`: claim schemas and lifecycle states.
- `bailey_os/evidence`: evidence schemas, mapping, IDs, integrity.
- `bailey_os/critic`: worker output critique and risk/correction model.
- `bailey_os/ralph`: routing state machine and transition policy.
- `bailey_os/reporter`: final report construction and rendering.

### Boundary rules
- No module may bypass schema validation.
- No report renderer may emit unverified factual claims.
- Plugins/tools can extend inputs and actions but cannot change core decision state semantics.
- Context and evidence stores are append-only within run scope (mutations require explicit policy path).

---

## 4) Data Schemas (Minimum Required)

### Run schema
- `run_id`
- `project_id`
- `started_at`
- `ended_at`
- `status`
- `events[]`

### Claim schema
- `claim_id`
- `run_id`
- `claim_text`
- `claim_type`
- `source`
- `impact`
- `evidence_required`
- `evidence_ids[]`
- `status`
- `confidence`
- `created_at`

Claim status enum:
- `unverified`
- `supported`
- `partially_supported`
- `unsupported`
- `contradicted`
- `inference`
- `needs_human_review`

### Evidence schema
- `evidence_id`
- `run_id`
- `source_type` (file/url/model/tool)
- `locator` (path+line, URL, message id, etc.)
- `content_hash`
- `captured_at`
- `metadata`

### Critic result schema
- `artifact_id`
- `checks[]`
- `risks[]`
- `corrections[]`
- `decision_recommendation`
- `confidence`

### Ralph decision schema
- `artifact_id`
- `current_state`
- `next_state`
- `rationale`
- `required_actions[]`
- `timestamp`

---

## 5) Agent Packet Protocol

Each packet must include:
1. Mission
2. Context
3. Inputs
4. Output paths
5. Interfaces/contracts touched
6. Acceptance tests
7. Non-goals
8. Failure modes
9. Critic checks
10. Handoff contract

Canonical packet template fields:
- `packet_id`
- `pod`
- `role`
- `dependencies`
- `estimated_scope`
- `risk_level`
- `deliverables`
- `acceptance_tests`
- `critic_checks`
- `ralph_decision_criteria`

Rule: **Work packets are durable assets; agents are disposable executors.**

---

## 6) 100-Agent Pod Map

Use 10 pods of 10 roles each.

- Pod 0: Control / architecture / integration
- Pod 1: CLI and runtime
- Pod 2: Context loading and project model
- Pod 3: Evidence and claim system
- Pod 4: Critic-loop and Ralph router
- Pod 5: PromptSpeak and skill system
- Pod 6: Plugin and tool framework
- Pod 7: Business process and functional specs
- Pod 8: Testing / QA / validation
- Pod 9: Documentation / packaging / demos

Per-pod role set:
1. lead architect
2. interface-contract agent
3. implementation agent
4. test agent
5. critic agent
6. documentation agent
7. security agent
8. integration agent
9. edge-case agent
10. cleanup/refactor agent

---

## 7) Build Waves (Staged Concurrency)

### Wave 0 — Control documents
Agents: Pod 0

Outputs:
- `BAILEY_OS_SPEC.md`
- `ARCHITECTURE.md`
- `MODULE_CONTRACTS.md`
- `BUILD_ORDER.md`
- `TRACEABILITY_MATRIX.md`

Gate: no downstream coding until Wave 0 artifacts pass critic checks.

### Wave 1 — Spine skeleton
Agents: Pods 1–3

Outputs:
- CLI skeleton
- Context loader
- Claim/evidence schemas
- Run logger
- Baseline tests

### Wave 2 — Validation engine
Agents: Pod 4 + Pod 8

Outputs:
- Critic loop
- Ralph router
- Test harness / CI / golden tests

### Wave 3 — Extension surfaces
Agents: Pods 5–6

Outputs:
- PromptSpeak parser/linter/runtime
- Skills registry/runner
- Plugin and tool framework
- `repo-audit` and `claim-check` starter plugins

### Wave 4 — Productization
Agents: Pods 7 + 9

Outputs:
- Business-process specs
- Functional documentation
- Demo flow
- Packaging/handoff checklist

---

## 8) Acceptance Test Standards

Global release gates:
- Every module change includes tests.
- All schema objects serialize/deserialize and validate.
- CLI smoke tests pass for core commands.
- Traceability from feature → test → docs exists.
- Final report blocks unverified factual claims.

Minimum required scenario tests:
1. `bailey init` creates expected files.
2. `bailey scan` returns stable JSON.
3. Claims are atomic and schema-valid.
4. Evidence IDs are unique within a run.
5. Unsupported claims are blocked from final outputs.
6. Ralph routes deterministically for canonical cases.
7. Report includes decision, evidence map, and unresolved risks.

---

## 9) Critic-Loop Standard

Each artifact must produce:
- `claim`: what is asserted
- `evidence`: what proves/grounds it
- `test`: what verifies behavior
- `risk`: what can fail
- `correction`: what to do if it fails
- `ralph_decision`: route outcome

Critic tiers:
1. deterministic checks (schema/contract/coverage)
2. heuristic checks (atomicity/completeness)
3. LLM checks (clarity, contradiction detection)

Any failed deterministic check prevents SHIP.

---

## 10) Ralph Routing Standard

Allowed states:
- `SHIP`
- `REVISE`
- `RETRY_WITH_NARROWER_SCOPE`
- `HOLD_FOR_EVIDENCE`
- `HUMAN_REVIEW`
- `PROMOTE_TO_MEMORY`
- `ARCHIVE`

Routing principles:
- Prioritize deterministic evidence sufficiency.
- Escalate to `HUMAN_REVIEW` for unresolved contradictions or policy conflicts.
- Allow `PROMOTE_TO_MEMORY` only when stability and repeatability thresholds are met.
- Use `RETRY_WITH_NARROWER_SCOPE` when failure is caused by over-broad packet scope.

---

## 11) First Milestone: `bailey audit-repo .`

Milestone objective: prove end-to-end spine viability.

Command:
- `bailey audit-repo .`

Expected report sections:
1. Project identity
2. File inventory
3. README claims
4. Detected entrypoints
5. Tests found
6. Missing tests
7. Unsupported claims
8. Evidence map
9. Critic findings
10. Ralph decision

Definition of done:
- Reproducible output format
- Explicit claim/evidence linkage
- Deterministic critic checks executed
- Ralph decision recorded with rationale

---

## 12) Explicit Non-Goals for Initial Build

Out of scope until spine passes all gates:
- SAP/NetSuite/ERP production plugins
- autonomous browser automation
- expansive long-term memory strategies beyond controlled promotion
- broad MCP integrations not required for first milestone

---

## 13) Master Swarm Brief Package

Prepare this package before launching a large implementation swarm:

```text
bailey-os-swarm-brief/
  00_MASTER_BRIEF.md
  01_ARCHITECTURE.md
  02_BUILD_ORDER.md
  03_MODULE_CONTRACTS.md
  04_AGENT_PACKET_PROTOCOL.md
  05_ACCEPTANCE_TEST_STANDARD.md
  06_CRITIC_LOOP_STANDARD.md
  07_RALPH_ROUTER_STANDARD.md
  agent_packets/
    000-system-architecture.md
    ...
    100-final-integration-critic.md
```

This package is the control plane for any agent executor system (Claude Code, Codex, or equivalent).
