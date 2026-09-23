# Rule catalogue

`scripts/dsh-gate` reads a dsh session log (JSONL) and answers one
question: *may this turn close?* Every rule is a pure function of the log
plus the adapter gates it can run - no model, no network.

Two severities:

- **fail** - the turn owes a repair round. Exit 1.
- **warn** - visible degradation, not fatal by default. Exit 1 only with
  `--strict`.

## Built-in rules

| Rule | Severity | Fires when |
| --- | --- | --- |
| `failing-tool` | fail | a `tool/result` event in this turn has a non-zero `exit` - the work is red regardless of what the report says |
| `adapter-error` | warn | a configured adapter could not run (script missing, unparseable output) - the check silently did not happen, so it is reported, never treated as clean |

## Adapters

Adapters are the family gates, invoked with `--format json` and their
findings re-tagged with `"adapter"`:

| Adapter | Source | Rules it contributes |
| --- | --- | --- |
| `prove-it` | assistant messages joined into one report | `unproven-claim`, `bad-evidence`, `evidence-mismatch` (fail), `weasel` (warn) |
| `testgate` | scan of `--path` when `--testgate` is set | `empty-test`, `no-assertion`, `tautology`, `test-off` (fail), `conditional-assert`, `expected-fail`, ... (warn) |

The adapter's own severity mapping is authoritative - dsh-gate does not
reclassify. Exit code of the verdict: any `fail` finding blocks; warns
block only with `--strict`.

## The question bypass

If the turn's **last** assistant message ends with `?`, the verdict is
immediately `{"ok": true, "question": true}` with zero findings - a turn
asking the user something is never forced into a repair round. This
mirrors `gate.skipWhenAskingUser` in LLM verifier plugins, implemented as
a rule instead of a prompt instruction.

## Reading the log

- Consumed event types: `assistant/attempt` and `assistant/message`
  (their `content`/`text`), `tool/result` (`exit`/`exit_code`, `tool`,
  `argv`, `output`/`error`).
- Unparseable JSONL lines are skipped (a torn tail after a crash must not
  fail the gate on syntax).
- A missing `--log` file is a usage error (exit 2): there is no turn to
  judge.

## Escape hatch

None on the verdict itself - a repair round is the intended path. The
adapters keep their own escapes (`# prove-it: allow`, `# testgate: allow`),
which apply inside their scans and therefore flow through unchanged.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | close the turn (clean, question-only, or warnings without `--strict`) |
| `1` | repair and re-run: at least one fail (or any warning with `--strict`) |
| `2` | usage error - missing log, bad flags |
