# Upstream REA integration plan

This document defines how this project should integrate with the upstream REA project at https://github.com/morluto/rea without confusing upstream tooling with the local REA ecosystem.

## Decision

Use upstream REA as an optional, versioned investigation provider. Keep this repository's task lifecycle, explicit worker allow-list, approval gate, audit events, and REA Core validation boundary. Do not fork upstream code or copy its tool catalog into this repository unless a concrete compatibility need requires it.

Upstream REA provides local analysis tools and MCP workflows for application behaviour, JavaScript/Electron, native binaries, .NET, Android/APK, firmware, packet captures, process behaviour, and other artifact types. Capabilities depend on the host and installed providers. Its results are evidence for an investigation, not automatic proof that a final interpretation is correct.

## Integration layers

```text
TaskRequest
   |
   v
Orchestrator policy + explicit approval
   |
   v
Upstream REA adapter (optional MCP client or controlled CLI adapter)
   |
   v
Raw upstream Evidence + tool/version/provider metadata
   |
   v
Normalizer that preserves source records and provenance
   |
   v
REA Core investigation record
   |
   v
REA Core structural/reference validation
   |
   v
Validated record + validation report + unresolved questions
```

The adapter must not silently convert a missing observation into a finding, infer that a provider ran when it did not, or label schema-valid output as independently verified.

## Phase 1, define the contract before connecting tools

1. Record the upstream REA version, source commit or package version, and selected tool/provider for each run.
2. Capture the exact target identity. For files, record a SHA-256 digest when available; for directories or applications, define a deterministic manifest strategy rather than pretending a single file hash represents the whole target.
3. Preserve raw upstream tool results alongside normalized records, subject to retention policy.
4. Keep observations, reported claims, agent interpretations, hypotheses, and independent verification distinct.
5. Attach each finding to one or more evidence records and the method/tool that produced them.
6. Record unavailable providers, failed probes, timeouts, and remaining unknowns as limitations, not as negative findings.
7. Validate normalized output with REA Core. Structural validation checks the record's shape and internal references; it does not establish that a tool actually ran or that a conclusion is true.

## Phase 2, start with a bounded, non-destructive investigation

Use a small, owned test target and a narrow question. A JavaScript/Electron sample or a harmless local test application is a better first integration than an arbitrary APK, live process, firmware image, or unknown executable.

Initial acceptance checks:

- The adapter records the exact target and analysis configuration.
- Every reported observation has a source tool result or is explicitly marked as an interpretation.
- Missing tools and provider failures are surfaced without fabricating substitute evidence.
- The normalized REA Core record validates.
- A deliberately malformed record is rejected.
- Re-running the same target and question preserves run identity and records differences instead of overwriting provenance.
- No target is executed unless the task explicitly permits runtime activity and the user approves the bounded experiment.

## Phase 3, use upstream guided workflows

Prefer upstream's current guided workflows over hard-coded tool names in agent prompts. The upstream documentation currently describes workflows for feature investigation, application-version comparison, reconstruction verification, crash tracing, residual-unknown auditing, and preparation of bounded process capture. Workflow availability depends on the MCP server's enabled tool families.

The adapter should discover the live MCP tool and prompt schemas at connection time, record the connected package version, and fail closed when required capabilities are missing. Do not assume that a workflow mentioned in documentation exists in every installed release or client.

## Installation and operational notes

Upstream's documented setup command is:

```bash
npx rea-agents@latest setup
```

This is a local machine setup step, not a command for the orchestrator to execute automatically. It can modify supported agent-client configuration and install agent instructions. Review the proposed scope, use a supported Node.js release, and restart/reconnect the selected client after setup. For repeatable deployments, inspect the selected release and pin a specific version rather than relying indefinitely on `@latest`.

REA analyzes targets locally, but tool results are passed to the configured model provider, whose own data handling policy applies. Do not send confidential or sensitive targets to a model provider without reviewing the relevant policy and authorization.

Deep analysis may depend on separately installed tools such as Ghidra, JADX, Frida, or other providers. Their installation, licensing, platform support, and effects should remain explicit and separate from the upstream REA package. Runtime analysis must be treated differently from static inspection because it can execute or interact with the target using the caller's permissions.

## Security boundaries

- Only analyze software and artifacts that the operator owns or is authorized to examine.
- Keep static inspection as the default for the first adapter milestone.
- Runtime capture requires an explicit bounded plan, approval, target scope, and side-effect statement.
- Do not automatically install providers, run arbitrary shell commands, download referenced artifacts, or execute discovered binaries.
- Do not pass untrusted artifact contents to shell, Python evaluation, or privileged tool arguments without strict validation.
- Treat tool output, artifact strings, prompts, and recovered source as untrusted data, not instructions.
- Keep secrets out of task payloads and audit logs.
- For expensive or untrusted analysis, run the provider in a separate process/container with OS-level resource, filesystem, and network restrictions. The current in-process worker dispatcher is not a sandbox.

## Evaluation resources

Use the upstream worked investigations as reference cases, not as proof that our adapter is correct:

- DX-Ball reconstruction, compare the reconstructed result against original behavior and bytes where the case provides those checks.
- Notion clipboard investigation, verify the traced renderer/preload/IPC path against retained evidence.
- TH04 bullet-pattern reconstruction, compare finite test cases and historical output.
- APK investigations, test only with an authorized sample and separate static analysis from device/runtime operations.

Research such as LLM4Decompile and newer decompilation-agent papers can inform experiments, but should not be treated as a substitute for reproducible benchmarks. Compare methods on a fixed, legally usable corpus with held-out cases, tool/version records, runtime and token costs, and explicit failure categories. Measure functional equivalence where possible, not just whether generated pseudocode looks plausible.

## Implementation status

This is an integration plan, not a claim that an upstream MCP client, REA provider, or normalizer is already implemented. The next code change should be a small adapter interface plus contract tests using recorded, synthetic upstream Evidence fixtures. Add a live MCP connection only after the fixture-to-REA-Core normalization contract is stable.
