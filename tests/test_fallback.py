import os
import unittest
from unittest import mock

from aicl import vendors
from aicl.webchat import _transcript


def recorder(name, log):
    def ask(system, history):
        log.append(name)
        return f"(T {name}.1>x true)"
    return ask


class FallbackTests(unittest.TestCase):
    def run_turns(self, api_factory, n=2):
        log, notes = [], []
        ask = vendors.with_web_fallback("gemini", api_factory, lambda: recorder("web", log), notes.append)
        for i in range(n):
            ask("SYS", [{"role": "user", "content": f"turn {i}"}])
        return log, notes, ask

    def test_api_that_works_is_never_replaced(self):
        log = []
        got, notes, _ = self.run_turns(lambda: recorder("api", log))
        self.assertEqual(log, ["api", "api"])
        self.assertEqual(notes, [])

    def test_missing_key_switches_to_the_browser(self):
        def no_key():
            raise RuntimeError("GEMINI_API_KEY is not set")
        log, notes, ask = self.run_turns(no_key)
        self.assertEqual(log, ["web", "web"])
        self.assertEqual(len(notes), 1)
        self.assertIn("switching this role to the browser version", notes[0])
        self.assertIn("is not set", ask.state["why"])

    def test_quota_or_dns_failure_mid_run_switches_for_good(self):
        for err in ("429 RESOURCE_EXHAUSTED quota", "httpx.ConnectError: [Errno 11002] getaddrinfo failed"):
            calls = []
            def api(system, history, err=err):
                calls.append(1)
                if len(calls) > 1:
                    raise RuntimeError(err)
                return "(T api.1>x true)"
            log, notes = [], []
            ask = vendors.with_web_fallback("gemini", lambda: api, lambda: recorder("web", log), notes.append)
            outs = [ask("S", [{"role": "user", "content": str(i)}]) for i in range(3)]
            self.assertEqual(outs[0], "(T api.1>x true)")
            self.assertEqual(log, ["web", "web"])          # the failed turn is retried on the web, then stays there
            self.assertEqual(len(calls), 2)

    def test_a_bad_answer_is_not_an_outage(self):
        def api(system, history):
            raise ValueError("model returned nonsense")
        ask = vendors.with_web_fallback("gemini", lambda: api, lambda: recorder("web", []), lambda s: None)
        with self.assertRaises(ValueError):
            ask("S", [{"role": "user", "content": "x"}])

    def test_force_web_skips_the_api(self):
        with mock.patch.dict(os.environ, {"AICL_FORCE_WEB": "gemini"}):
            log, notes, _ = self.run_turns(lambda: self.fail("the API must not be built"), n=1)
        self.assertEqual(log, ["web"])

    def test_a_switch_mid_conversation_carries_the_earlier_turns(self):
        text = _transcript("ROLE", [{"role": "user", "content": "first"}, {"role": "assistant", "content": "(K a.1>b ^b.1)"},
                                    {"role": "user", "content": "second"}])
        self.assertTrue(text.startswith("ROLE"))
        self.assertIn("[assistant]\n(K a.1>b ^b.1)", text)
        self.assertTrue(text.endswith("second"))

    def test_claude_has_no_web_fallback(self):
        self.assertNotIn("claude", vendors.WEB_SITE)
        self.assertEqual(vendors.WEB_SITE, {"gemini": "gemini", "muse": "meta"})


if __name__ == "__main__":
    unittest.main()
