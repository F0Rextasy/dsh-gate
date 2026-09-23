# dsh-gate

**An LLM verifier scores your turn with a model. dsh-gate reads the session
log and tells you the same thing in milliseconds, for free.** A
deterministic turn gate for [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)
(`dsh`): claims must carry executed evidence, tests must be able to fail,
red tool calls block - and a question to the user never blocks.

## Why this exists

Verifier plugins (LLM-as-a-verifier, `dsh-verifier-gate`) answer "may this
turn close?" with a model call: minutes of thinking, logprobs, a dollar a
turn - and the verdict is a probability over letters. Half the gate's job
never needed a model at all: whether a claim has an exit code under it,
whether a test can fail, whether `npm test` exited 1 three steps ago.
Those are **facts in the log**. dsh-gate computes them exactly.

| Gate | Catches |
| --- | --- |
| **preflight** | `prod` in debug, `example.com` URLs, wildcard CORS, flat `requirements` |
| **prove-it** | claims (`all tests pass`) with no executed command + exit code behind them |
| **testgate** | tests that can never fail - the green that proves nothing |
| **shipcheck** | empty/mislabeled wheels, unimportable artifacts |
| dsh-gate: deterministic turn gate for dsh session logs *(this repo)* | red turns closing green |

Family contract: one Python script, stdlib only, exit 0 = close the turn,
1 = repair round, 2 = usage error.

## Install

```bash
git clone https://github.com/F0Rextasy/dsh-gate
python scripts/dsh-gate session --log "$SESSION_JSONL" --testgate
```

Wire it where a turn ends (`agent/turn-stopping`, a wrapper script, a CI
job over recorded logs). The `message` subcommand emits the plugin-style
line on stderr:

```console
$ python scripts/dsh-gate message --log turn.jsonl
{"ok": false, "counts": {"fail": 1, "warn": 0}, ...}
[dsh-gate] Verification failed: 1 failing, 0 warnings -- claim with no "$ command" ... -- repair and re-run
[exit 1]
```

## What it checks

1. **Claims need evidence** - assistant messages are joined into a report
   and passed to the family's **prove-it**: `all tests pass` without a
   `$ command` + `[exit N]` block under it blocks the turn.
2. **Tests must be able to fail** (`--testgate`) - **testgate** scans the
   test tree for `assert True`, empty bodies, skip-disabled tests.
3. **Red tools block** - any `tool/result` with a non-zero exit in the log
   blocks as `failing-tool`.
4. **Questions never block** - last assistant message ends in `?` →
   `{"ok": true, "question": true}`, always. (The LLM gates ship this as
   `skipWhenAskingUser`; here it is a rule, not an instruction.)

No model, no network, no logprobs. The verdict is a pure function of the
log: the same log gates the same way, every time.

## Evidence (real outputs)

Eight contract tests over fake session logs:

```console
$ python -m unittest discover -s tests -v
test_failing_tool_blocks (test_dsh_gate.DshGateContract) ... ok
test_message_command_posts_to_stderr (test_dsh_gate.DshGateContract) ... ok
test_missing_log_is_usage_error (test_dsh_gate.DshGateContract) ... ok
test_proven_claims_pass_with_exit_zero (test_dsh_gate.DshGateContract) ... ok
test_questions_never_block (test_dsh_gate.DshGateContract) ... ok
test_testgate_collects_pytest_findings (test_dsh_gate.DshGateContract) ... ok
test_unproven_claim_blocks_with_exit_one (test_dsh_gate.DshGateContract) ... ok
test_verdct_json_reports_structure (test_dsh_gate.DshGateContract) ... ok

----------------------------------------------------------------------
Ran 8 tests in 1.411s

OK
[exit 0]
```

Each test builds a JSONL log (user, attempts, tool results), runs the real
CLI, and asserts the observable exit code and JSON - nothing internal.

## Verdict

```json
{
  "ok": false,
  "counts": {"fail": 1, "warn": 0},
  "findings": [
    {"adapter": "prove-it", "rule": "unproven-claim", "severity": "fail",
     "file": "<stdin>", "line": 1,
     "message": "claim with no `$ command` + `[exit N]` block under it"}
  ]
}
```

`adapter` says which family member spoke; everything else matches that
gate's own JSON contract. An adapter that cannot run is a visible
`adapter-error` **warn**, never a silent pass.

Full catalogue: [references/RULES.md](references/RULES.md).

## Layout

```text
dsh-gate/
+-- scripts/dsh-gate        # the gate (stdlib only, extension-less CLI)
+-- SKILL.md                # Agent Skill (Claude Code / Codex / Cursor)
+-- references/RULES.md     # rules, adapters, question bypass, exit codes
+-- tests/test_dsh_gate.py  # contract tests over fake session logs
```

## License

[MIT](LICENSE)
