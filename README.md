# REA Orchestrator

**Status, scaffold and design specification.**

REA Orchestrator is intended to route bounded investigation tasks to specialist REAs and tools. This repository documents the intended responsibility. It does not yet provide a complete orchestration engine.

## Intended responsibilities

- Accept a structured investigation request.
- Identify eligible specialist adapters.
- Check task constraints, permissions and required inputs.
- Create a bounded plan with explicit dependencies.
- Record dispatch, completion, failure and timeout states.
- Collect results using the REA Core contract.
- Leave consequential execution decisions under explicit operator control.

## Proposed task lifecycle

`proposed → approved → dispatched → completed | failed | blocked | cancelled`

Each task should record inputs, selected adapter, declared permissions, timeout, result references and execution status. Dispatch does not prove that a specialist performed valid work.

## Interfaces

The intended shared data contract is [REA Core](https://github.com/DerekWiner/rea-core). Tool integrations may use MCP adapters where appropriate, but this scaffold does not claim a complete MCP orchestration integration.

## Safety requirements

- Do not execute untrusted artifacts by default.
- Do not grant credentials or network access implicitly.
- Enforce timeouts and resource limits outside model prompts.
- Preserve provenance and error states.
- Make retries idempotent where practical.
- Require approval for high-impact actions.

## Current status and next milestone

Task routing, dependency scheduling, worker isolation, retries, durable state and production observability remain to be implemented and tested.

Build one deterministic local dispatcher for a mock specialist, using a REA Core record as input and output. Add tests for invalid input, timeout, failure and provenance before connecting external tools.
