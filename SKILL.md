---
name: dsh-gate
description: Deterministic turn gate for DeepSeek Harness (dsh) session logs. Use at the end of an agent turn before reporting success -- reads the JSONL session log, runs prove-it over assistant claims, optionally testgate over the tree, blocks turns with failing tool calls, and never blocks a question to the user. No model, no network, no logprobs.
license: MIT
compatibility: Requires Python 3.8+ and a dsh session log (JSONL). Runs in Claude Code, Codex, Cursor, and any Agent Skills compatible client.
metadata:
  author: F0Rextasy
  version: "1.0"
---

# dsh-gate

LLM verifiers score a finished turn with a model that costs minutes and
dollars per verdict. dsh-gate answers the same question - *may this turn
close?* - deterministically, from the session log alone, in milliseconds.

## The one rule

You may not close a turn until:

```bash
python scripts/dsh-gate session --log <session.jsonl> --testgate
```

exits 0. Exit 1 means the turn owes a repair round: read the findings,
fix, re-run. Exit 2 means the log path is wrong.

## What it checks (no model anywhere)

1. **Claims need evidence** (prove-it adapter) - every `all tests pass` /
   `fixed` / `green` in the assistant's messages must carry a
   `$ command` + `[exit N]` block. Floating claims block the turn.
2. **Tests must be able to fail** (testgate adapter, `--testgate`) - the
   test tree is scanned for theater tests before the turn can claim green.
3. **Red tools block** - any `tool/result` in the log with a non-zero exit
   that the turn did not acknowledge blocks with `failing-tool`.
4. **Questions never block** - a turn whose last assistant message ends in
   `?` closes immediately (`"question": true`), the same rule the LLM
   gates ship as `skipWhenAskingUser`.

## Protocol

1. **Find the log** - the turn's `session.jsonl` (v1+: `session.v1.jsonl`
   and up; dsh stores them under `$DSH_HOME/sessions`).
2. **Gate**:

```bash
python scripts/dsh-gate session --log "$LOG" --testgate
```

3. **Wire it** - mount as a hook on `agent/turn-stopping`, or call it from
   a wrapper script. The `message` subcommand prints the same JSON on
   stdout and the plugin-style line on stderr:

```
[dsh-gate] turn verified: clean -- 3 findings checked, 0 blocking
```

## Verdict shape

```json
{
  "ok": false,
  "counts": {"fail": 1, "warn": 0},
  "findings": [
    {"adapter": "prove-it", "rule": "unproven-claim", "severity": "fail",
     "file": "<stdin>", "line": 1, "message": "claim with no $ command ..."}
  ]
}
```

`adapter` names which family member produced the finding; `rule`,
`severity`, `file`, `line` match that gate's own JSON contract. An
adapter that cannot run is a **warn** (`adapter-error`), never a silent
pass - a gate that vanished must be visible.

## Configuration

Flags are the configuration (no YAML, no hot reload - it is a CLI):

| Flag | Effect |
| --- | --- |
| `--no-prove` | skip the claim adapter |
| `--prove-script CMD...` | prove-it command (auto-found in a sibling checkout) |
| `--testgate` | also scan `--path` for theater tests |
| `--testgate-script CMD...` | testgate command |
| `--path DIR` | test tree for `--testgate` (default `.`) |
| `--strict` | warnings block too |

Without `--prove-script`, the adapter looks for `prove-it/scripts/prove.py`
next to this repo, then in the cwd; missing is a visible warn.

## Scope

Reads the log only - it never writes to a session, never spawns a model,
never touches the network. Event types consumed: `assistant/attempt`,
`assistant/message`, `tool/result`. The verdict is a pure function of the
log, so the same log always gates the same way.
