"""Contract tests for dsh-gate. Run: python -m unittest discover -s tests -v

Every test drives the real adapter against a fake session log (no harness
needed) and asserts the exit code and JSON a consumer would observe.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "dsh-gate")


def run_cli(*args):
    proc = subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def make_log(tmp, events):
    path = os.path.join(tmp, "session.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")
    return path


def user(text):
    return {"type": "user/message", "text": text}


def attempt(content):
    return {"type": "assistant/attempt", "content": content}


def tool(name, argv, exit_code, output="", err=""):
    return {"type": "tool/result", "tool": name, "argv": argv,
            "exit": exit_code, "output": output, "error": err}


class DshGateContract(unittest.TestCase):
    def test_proven_claims_pass_with_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_log(tmp, [
                user("task: wire the retry loop"),
                attempt("Reworked the retry loop so backoff is exponential."),
                tool("python", ["-c", "print(1)"], 0, "1\n"),
                attempt("All tests pass:\n```console\n$ python -m unittest discover -s tests\n[exit 0] OK\n```"),  # noqa: E501
            ])
            code, out, _ = run_cli("session", "--log", path, "--prove",
                                   "--prove-script", "python",
                                   os.path.join("prove-it", "scripts",
                                                "prove.py"),
                                   "--no-color")
        self.assertEqual(code, 0, out)
        self.assertIn('"ok": true', out)

    def test_unproven_claim_blocks_with_exit_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_log(tmp, [
                user("task: fix it"),
                attempt("Should be fixed now."),
            ])
            code, out, _ = run_cli("session", "--log", path, "--prove",
                                   "--prove-script", "python",
                                   os.path.join("prove-it", "scripts",
                                                "prove.py"),
                                   "--no-color")
        self.assertEqual(code, 1, out)
        self.assertIn('"ok": false', out)
        self.assertIn("unproven-claim", out)

    def test_verdict_json_reports_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_log(tmp, [
                user("task: fix it"),
                attempt("Should be fixed now."),
            ])
            code, out, _ = run_cli("session", "--log", path, "--no-color")
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertFalse(data["ok"])
        self.assertIn("findings", data)
        self.assertGreater(len(data["findings"]), 0)
        self.assertEqual(data["findings"][0]["adapter"], "prove-it")

    def test_testgate_collects_pytest_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            sub = os.path.join(tmp, "t")
            os.makedirs(sub)
            with open(os.path.join(sub, "test_x.py"), "w") as fh:
                fh.write("def test_x():\n    assert True\n")
            code, out, _ = run_cli("session", "--path", sub,
                                   "--testgate",
                                   "--testgate-script", "python",
                                   os.path.join("testgate", "scripts",
                                                "testgate.py"),
                                   "--no-color")
        self.assertEqual(code, 1, out)
        self.assertIn("tautology", out)

    def test_missing_log_is_usage_error(self):
        code, _, err = run_cli("session", "--log",
                               os.path.join("nope", "missing.jsonl"))
        self.assertEqual(code, 2)
        self.assertIn("not found", err)

    def test_message_command_posts_to_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_log(tmp, [user("task: say hi")])
            code, out, err = run_cli("message", "--log", path, "--no-color")
        self.assertEqual(code, 0)
        self.assertIn('"ok": true', out)
        self.assertIn("dsh-gate", err)

    def test_questions_never_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_log(tmp, [
                user("task: pick one"),
                attempt("Should we use A or B?"),
            ])
            code, out, _ = run_cli("session", "--log", path, "--prove",
                                   "--prove-script", "python",
                                   os.path.join("prove-it", "scripts",
                                                "prove.py"),
                                   "--no-color")
        self.assertEqual(code, 0, out)
        self.assertIn("question", out)

    def test_failing_tool_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_log(tmp, [
                user("task: run it"),
                tool("npm", ["test"], 1, "", "2 failed"),
                attempt("Tests are green."),
            ])
            code, out, _ = run_cli("session", "--log", path, "--prove",
                                   "--prove-script", "python",
                                   os.path.join("prove-it", "scripts",
                                                "prove.py"),
                                   "--no-color")
        self.assertEqual(code, 1, out)
        self.assertIn("failing tool call", out)


if __name__ == "__main__":
    unittest.main()
