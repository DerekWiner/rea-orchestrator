# REA build and automation roadmap

## Current baseline

- The orchestrator dispatches to explicitly registered in-process workers, applies a local approval gate, records optional JSONL events, and has tests.
- The upstream REA capture normalizer converts a versioned capture envelope into an REA Core v1-shaped record. It is a normalizer, not an MCP client.
- REA Core validates investigation record structure and internal references offline.
- Upstream morluto/rea supplies its own MCP server, CLI and target-specific tools. Its installation and provider requirements are separate from our Python packages.

## Milestone A, establish a repeatable local environment

1. Install Git, Python 3.10+, and Node.js at a version supported by the upstream REA release you select.
2. Clone rea-core and rea-orchestrator into a workspace.
3. Create a virtual environment in the orchestrator repository and install its test extra.
4. Run unit tests before changing anything.
5. Install upstream REA in a development environment, review the setup plan, and connect one supported agent client. Avoid running setup from inside a target repository.
6. Pick a harmless application or synthetic fixture that you are authorized to inspect.

Upstream's current README documents Node.js 22.x (>=22.23.4), 24.x (>=24.22.1), or 26.12.1+ with npm. Verify the exact minimum against the release you install because the project evolves quickly.

## Milestone B, verify the new capture adapter

From the orchestrator repository:

```bash
python -m pip install -e ".[test]"
python -m pytest
```

The adapter tests use synthetic data. They do not require an MCP server, model API key, Ghidra, Frida or a live target. The CLI can normalize and validate the included fixture with:

```bash
python -m pip install -e ".[test]" -e ../rea-core
rea-orchestrator --normalize-capture examples/upstream-rea-capture.json --validate-core > investigation.json
rea-core validate investigation.json
```

Do not mark a result as verified just because it passes schema validation.

## Milestone C, make one real, bounded investigation

1. Ask upstream REA to inspect a small JavaScript/Electron fixture or another static-analysis-friendly target.
2. Capture the exact tool names, provider version, timestamps, result summaries, raw result payloads, target identity and limitations into the capture envelope described in examples/upstream-rea-capture.json.
3. Normalize it with normalize_capture.
4. Validate the output with REA Core.
5. Compare every normalized observation with the retained raw tool output. Record missing or ambiguous mappings as limitations.
6. Repeat the same investigation and compare output. Preserve both runs rather than overwriting the original record.

The live MCP transport and direct mapping from upstream's evolving result schemas remain future work. Do not assume the synthetic envelope is an upstream-native wire format.

## Milestone D, connect a specialist REA

Use Crypto-REA or a narrow software investigation first. The adapter must return a versioned REA Core record, preserve artifact checksums and method metadata, cite evidence for every finding, and report unsupported claims as unresolved. Only after that contract works should the same pattern be applied to Bio-REA, where biological interpretations require domain-specific validation.

## Automation we should enable

### Already automatic

- GitHub Actions runs tests when files are pushed to the configured repository branches.
- The normalizer and unit tests run locally without paid model access.

### Configure in GitHub

- Protect the default branch with required CI checks if branch rules are available.
- Require review for changes to workflows, dependency declarations and release automation.
- Enable dependency/security alerts if available.
- Do not store model keys in source files, example captures or ordinary audit logs.

### Configure locally

- Keep a dedicated workspace and Python virtual environment.
- Install only the analysis providers required for the first target.
- Use versioned tool installations and retain version/commit information with each investigation.
- Store real artifacts and raw evidence outside the Git repository if they are confidential or large; commit only synthetic fixtures and sanitized examples.
- Review upstream setup changes before approving agent-client configuration modifications.

### Not automated yet

- Upstream REA MCP client transport inside our orchestrator.
- Automatic capture-envelope generation from upstream native tool results.
- REA Core validation wired directly into dispatcher completion.
- Durable job queue, process/container isolation, credentials broker, distributed concurrency or persistent idempotency.
- Automatic scheduling of investigations or unattended live-target execution.

These are separate engineering milestones, not configuration toggles. The current dispatcher executes workers in-process, and its timeout only bounds caller wait time. Do not use it as a security sandbox or run untrusted code in it.

## Operating rule

Static analysis first. Runtime analysis only for an authorized target, with a stated scope, approval, side-effect assessment and isolated execution where practical. Model-generated interpretations remain interpretations until independently checked.
