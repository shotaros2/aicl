import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from koine.cli import main

EX = Path(__file__).resolve().parents[1] / "examples"


def run(*argv):
    out = io.StringIO()
    code = 0
    with redirect_stdout(out):
        try:
            main(list(argv))
        except SystemExit as e:
            code = e.code or 0
    return code, out.getvalue()


class CliTests(unittest.TestCase):
    def test_fmt(self):
        code, out = run("fmt", str(EX / "02_deploy.koine"))
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[0], "(ask #a.1 @a>@b (deploy-status build-4821 $s :finished-at $at))")

    def test_json_and_hash(self):
        code, out = run("json", "--compact", str(EX / "02_deploy.koine"))
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)), 6)
        code, out = run("hash", str(EX / "02_deploy.koine"))
        self.assertEqual(len(out.split()), 6)

    def test_check_passes_with_known_terms(self):
        code, out = run("check", str(EX / "02_deploy.koine"),
                        "--known", "deploy-status", "--known", "rollout", "--known", "error-rate")
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_check_reports_warnings_without_known_terms(self):
        code, out = run("check", str(EX / "02_deploy.koine"))
        self.assertEqual(code, 0)
        self.assertIn("unresolved-term", out)

    def test_check_fails_on_error(self):
        bad = EX.parent / "tests" / "_bad.koine"
        bad.write_text("(ok #b.1 @b>@a)\n", encoding="utf-8")
        try:
            code, out = run("check", str(bad))
        finally:
            bad.unlink()
        self.assertEqual(code, 1)
        self.assertIn("reply-required", out)

    def test_stats(self):
        code, out = run("stats", str(EX / "05_subscription.koine"))
        self.assertEqual(code, 0)
        self.assertIn("nl ratio", out)


if __name__ == "__main__":
    unittest.main()
