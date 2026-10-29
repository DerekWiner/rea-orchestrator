# Specialist adapter contract

This document defines the next integration seam. It is a design contract, not a claim that REA Core validation or specialist REA execution is already wired into the dispatcher.

## Current dispatcher interface

A registered worker is an in-process callable that accepts one Python dictionary and returns one JSON-serializable dictionary. The worker name is registered by application code. A task cannot supply a module path, Python expression, shell command, or remote endpoint.

## Target adapter interface

A specialist adapter should accept a validated task envelope and return a REA Core investigation record, or a structured failure that does not masquerade as a finding. The adapter should preserve:

- Stable task and investigation identifiers
- Artifact source references and cryptographic checksums where available
- Explicit evidence type, timestamp, and provenance
- Method identifiers and execution mode
- Finding-to-evidence references
- Limitations, unresolved questions, and error states

## Required validation flow

1. Parse and validate the task envelope.
2. Apply approval and capability policy before dispatch.
3. Dispatch only to a registered adapter.
4. Treat all worker output as untrusted data.
5. Validate the returned investigation record with `rea-core` before accepting it.
6. Store the raw worker output and validation report separately where retention policy permits.
7. Mark the result as invalid or failed when validation fails. Never silently repair provenance or fabricate missing evidence.

## What is intentionally not included yet

- No direct dependency on the `rea-core` package
- No network or MCP client
- No durable queue or distributed locks
- No cross-process worker isolation
- No secret storage or permission broker
- No automatic retries or parallel dependency graph execution

These should be added behind tested interfaces, not embedded into the current demo worker.
