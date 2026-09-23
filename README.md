# dsh-gate

**Deterministic turn gate for DeepSeek Harness.** Claims need evidence, tests must be able to fail, red tool calls block the turn - and a question to the user never blocks anything. Reads the session log (JSONL), runs the sibling gates over the finished turn, prints a verdict: JSON for machines, one human line for the terminal. No model, no network, no logprobs - the opposite of an LLM verifier.

[![tests](https://img.shields.io/github/actions/workflow/status/F0Rextasy/dsh-gate/test.yml?branch=master&label=tests&style=flat-square&color=3fb950)](https://github.com/F0Rextasy/dsh-gate/actions/workflows/test.yml)
[![python](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white&style=flat-square)](https://www.python.org/)
[![verdicts](https://img.shields.io/badge/verdicts-deterministic-3fb950?style=flat-square)](#what-it-will-never-do)
[![skills](https://skills.sh/b/F0Rextasy/dsh-gate?style=flat-square)](https://skills.sh/F0Rextasy/dsh-gate)
[![license](https://img.shields.io/badge/license-MIT-3fb950?style=flat-square)](LICENSE)

![dsh-gate verdict on a red turn](assets/demo.svg)

## Why this exists

An agent turn ends with "done - all tests pass." Behind it: `pytest` exited 1, the tool result in the session log says so, and the harness was about to close the turn green anyway. LLM verifiers answer this with another LLM call - same failure surface, new bill. The session log already contains the facts: an attempt's text (claims), tool results with exit codes (reality), user messages (questions). `dsh-gate` reads those facts and applies rules - deterministically, in milliseconds, offline.

## Quick start

```bash
# install the skill into any agent (Claude Code, Codex, Cursor, OpenCode, ...):
npx skills add F0Rextasy/dsh-gate

# or run it directly:
git clone https://github.com/F0Rextasy/dsh-gate
python dsh-gate/scripts/dsh-gate session --log session.jsonl   # verdict JSON
python dsh-gate/scripts/dsh-gate message --log session.jsonl   # + gate text on stderr
```

| Exit | Meaning |
| --- | --- |
| `0` | turn verified: no blocking finding |
| `1` | verdict fails: unproven claim, failing tool call, vacuous test |
| `2` | usage error (missing/unreadable log) |

## How it decides

```mermaid
flowchart TD
    A["session log (JSONL)"] --> B["events: user / assistant attempts / tool results"]
    B --> Q{"user message is a question?"}
    Q -- yes --> PASS["never blocks: questions pass"]
    B --> T{"tool result exit != 0?"}
    T -- yes --> X["FAIL failing-tool:<br/>the turn stays red"]
    T -- no --> C["claims = assistant attempt text"]
    C --> P["prove-it adapter:<br/>every claim needs $ cmd + [exit N]"]
    C --> G["testgate adapter (opt-in):<br/>tests must be able to fail"]
    P -- unproven --> X
    G -- vacuous test --> X
    P & G --> OK["ok: turn verified -- can close"]
```

Adapters: prove-it runs **on by default** (`--no-prove` to skip, `--prove-script` to point elsewhere); testgate is opt-in (`--testgate`). Missing adapter script degrades to a recorded warning, never a silent pass. Full rules: [references/RULES.md](references/RULES.md).

## Evidence (real output)

A session where the assistant claimed success, but `pytest` exited 1:

```console
$ python scripts/dsh-gate message --log session.jsonl --no-prove
{
  "ok": false,
  "counts": {
    "fail": 1,
    "warn": 0
  },
  "findings": [
    {
      "adapter": "dsh-gate",
      "rule": "failing-tool",
      "severity": "fail",
      "file": "",
      "line": 0,
      "message": "failing tool call bash pytest -q exited 1: 1 failed, 3 passed"
    }
  ]
}
[dsh-gate] Verification failed: 1 failing, 0 warnings -- failing tool call bash pytest -q exited 1: 1 failed, 3 passed -- repair and re-run
[exit 1]
```

With `--prove` the verdict additionally cites every unproven claim - file, line, and the missing evidence block. Contract tests drive the real adapter against fake session logs, no harness needed:

```console
$ python -m unittest discover -s tests -v
test_failing_tool_blocks (test_dsh_gate.DshGateContract) ... ok
test_message_command_posts_to_stderr (test_dsh_gate.DshGateContract) ... ok
test_missing_log_is_usage_error (test_dsh_gate.DshGateContract) ... ok
test_proven_claims_pass_with_exit_zero (test_dsh_gate.DshGateContract) ... ok
test_questions_never_block (test_dsh_gate.DshGateContract) ... ok
test_testgate_collects_pytest_findings (test_dsh_gate.DshGateContract) ... ok
test_unproven_claim_blocks_with_exit_one (test_dsh_gate.DshGateContract) ... ok
test_verdict_json_reports_structure (test_dsh_gate.DshGateContract) ... ok

----------------------------------------------------------------------
Ran 8 tests in 1.446s

OK
[exit 0]
```

Covered: proven-pass, red-tool block, question-never-blocks, unproven-claim, adapter findings, verdict JSON shape, missing log.

## Wire it in

As the close-turn check in the harness (post-turn hook), or in CI over a dumped session:

```bash
dsh-gate message --log "$SESSION" --path . --testgate || echo "turn stays open"
```

`--path` is the workspace the testgate adapter scans; verdict JSON goes to stdout, the human gate line to stderr.

## What it will never do

- Call a model to decide whether the turn is done - the log's exit codes are the ground truth.
- Block a question: anything shaped like a user-facing question passes by design.
- Pass silently when an adapter is missing: that is a recorded warning, visible in the verdict.

## One path, many gates — the family

Deterministic gates - one Python script each, stdlib, same exit contract:

| Repo | What its verdict means |
| --- | ---|
| [dsh-gate](https://github.com/F0Rextasy/dsh-gate) | the shell session actually ran - real commands, real files, real log |
| [sessionaudit](https://github.com/F0Rextasy/sessionaudit) | the session behaved - scope, secrets, destructive acts, self-contradicted claims |
| [cigate](https://github.com/F0Rextasy/cigate) | the workflows burn each minute once - pins, path filters, dedup, budget |
| [ci-triage](https://github.com/F0Rextasy/ci-triage) | one log, one verdict: regression / flaky / infra / pass |
| [docproof](https://github.com/F0Rextasy/docproof) | every README doc snippet is runnable, parsed, and verified in CI |
| [preflight](https://github.com/F0Rextasy/preflight) | the config is safe to ship - semantics, not syntax |
| [prove-it](https://github.com/F0Rextasy/prove-it) | every claim in this README is backed by real, captured output |
| [shipcheck](https://github.com/F0Rextasy/shipcheck) | the artifacts in `dist/` match `src/` - nothing stale ships |
| [testgate](https://github.com/F0Rextasy/testgate) | the tests that ran are the tests that exist - gaps, dupes, skips |
| [bandaid](https://github.com/F0Rextasy/bandaid) | the diff doesn't hide a silent failure - swallowed errors, dead guards |
| [wincompat](https://github.com/F0Rextasy/wincompat) | every path in the tree survives a Windows checkout |
| [compressproof](https://github.com/F0Rextasy/compressproof) | the context shrank without losing an answer - reversible compression, byte proof, answer-equivalence oracle |
| [uigate](https://github.com/F0Rextasy/uigate) | the UI stops looking like the same AI slop - measurable design-slop lint, WCAG + template tells |
| [aitell](https://github.com/F0Rextasy/aitell) | the prose stops reading as AI - deterministic AI-tell detection with a published confusion matrix |
| [route-drift](https://github.com/F0Rextasy/route-drift) | OpenAPI spec vs code routes drift gate |

## License

[MIT](LICENSE)
