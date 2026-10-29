# REA Orchestrator

**Status, runnable local prototype.** This repository now contains a small dispatcher for explicitly registered, in-process specialist workers. It is not a distributed scheduler, a production agent runtime, or a complete MCP integration.

## What works now

- Validates a bounded JSON task request and rejects unknown fields.
- Dispatches only to a worker registered by the application operator.
- Defaults to requiring explicit approval for each request.
- Records start and finish events as append-only JSON Lines when an audit path is configured.
- Captures worker exceptions, reports caller-side timeouts, and supports in-memory replay of successful idempotency keys.
- Includes a CLI and deterministic demo worker, with unit tests and GitHub Actions CI.
- Includes a versioned upstream REA capture normalizer that maps captured tool runs into REA Core v1-shaped records, with provenance hashes and explicit limitations.

## Quick start

Install Python 3.10 or later, then run from a clone of this repository.

```bash
python -m pip install -e ".[test]"
python -m pytest
rea-orchestrator --list-workers
```

Create `task.json`

```json
{
  "task_id": "demo-001",
  "specialist": "demo.echo",
  "input": {
    "question": "What evidence would verify this claim?"
  },
  "requires_approval": true,
  "timeout_seconds": 5,
  "idempotency_key": "demo-001"
}
```

Dispatch it only after explicit approval.

```bash
rea-orchestrator task.json --approve --audit ./run/events.jsonl
```

The built-in `demo.echo` worker returns the supplied payload. It does not call an LLM, search the web, run an experiment, or produce a verified finding.

## Task lifecycle

The request model records task identity, specialist name, JSON input, caller wait timeout, approval requirement, optional idempotency key, and namespaced metadata. Outcomes are `completed`, `failed`, or `timed_out`. Approval failures and unknown worker names are rejected before a worker is called.

The dispatcher does not automatically retry a failed worker. The idempotency cache is in memory only, applies only to successful results, and is not a durable exactly-once guarantee.

## Security boundaries and known limitations

- Worker names are allow-listed in application code. Task JSON cannot import code or register workers.
- Approval is a local API/CLI gate, not an identity system or cryptographic authorisation mechanism.
- The timeout limits how long the caller waits. Python cannot safely terminate a running thread, so a timed-out worker may continue running. This is not a sandbox.
- Workers execute in the same process and inherit its permissions. Do not register untrusted code. For untrusted or expensive work, use a separate process or container with operating-system resource limits and explicit filesystem/network policy.
- Audit JSONL is append-only by convention, not tamper-proof. It may contain task metadata and should be stored with appropriate access controls.
- The idempotency cache and registry are process-local. There is no durable queue, concurrency scheduler, distributed locking, worker health management, authentication, authorisation service, secrets broker, MCP transport, or database backend.
- The dispatcher does not yet run REA Core validation automatically at dispatch completion. The upstream capture normalizer can accept REA Core's validator as a callback, but callers must deliberately wire it in. The normalizer is not an MCP client and its capture envelope is our adapter contract, not an upstream-native wire format.

## Architecture

```text
JSON task request
       |
       v
TaskRequest validation
       |
       v
Approval gate ---- blocked before dispatch when not approved
       |
       v
Explicit WorkerRegistry
       |
       v
Bounded caller wait + outcome capture
       |
       v
DispatchResult + optional JSONL audit events
```

The intended contract is [REA Core](https://github.com/DerekWiner/rea-core). The next integration milestone is a specialist adapter that consumes a validated request, returns a REA Core investigation record, and preserves artifact/evidence provenance. MCP adapters can be added after this local interface is stable.

For the upstream investigation engine and its MCP workflows, see the [upstream REA integration plan](docs/upstream-rea-integration.md). The [capture fixture](examples/upstream-rea-capture.json) documents the adapter envelope and is entirely synthetic. The [automation roadmap](docs/automation-roadmap.md) separates completed functionality from operator setup and future work. Upstream REA is an optional provider, not a replacement for our task policy or REA Core validation.

## License

MIT. Worker integrations and third-party tools remain subject to their own licences and terms.
