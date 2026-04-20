# Security

## Responsible Disclosure

If you find a security issue, please do **not** file a public GitHub issue.

Email: chris.bailey@erp-access.com — include "SECURITY: MyPersona" in the subject line.

Expect an acknowledgment within 72 hours.

## What this tool does

MyPersona is an MCP server (stdio) that receives user messages from a host agent (Claude Code, Claude Desktop, or any MCP client) and stores emotional memory: mood readings, beliefs, and memory entries with decay. Data lives in local storage controlled by the user — not in a cloud service operated by this project.

## What this tool does NOT do

- It does not make outbound network calls. Mood detection, belief extraction, and gap analysis run locally against local data.
- It does not send user messages or stored memories to any third party.
- It does not store data in any location other than the local paths the user configures.
- It does not bypass the governance hold queue for high-intensity memories — those require an explicit `ps_hold_approve` call before storage.
- It does not expose the MCP tools over a network transport by default (stdio only).

## Known Considerations

- This server is designed to be run locally by a single user. If you wrap it in an HTTP transport and expose it, you are responsible for auth and isolation — any client that can call the tools can read or write any user's memory.
- Stored memories may contain highly personal content (crisis events, relationships, health). The local database is not encrypted at rest by default — rely on disk-level encryption (FileVault, LUKS) on the host.
- The `ps_get_audit_trail` tool returns the full decision history, including held-and-rejected memories. Treat the audit trail as sensitive.
- The gap analysis output (theatre score, predicted behavior) is a model inference, not a fact about the user. Do not ship it to third parties as if it were factual.
- Memory decay is time-based. If the system clock is manipulated, decay behavior will be wrong — not a security issue in itself, but worth knowing.

If you see evidence of any of the "does NOT do" items, that is a security issue — please report.
