import unittest
from types import SimpleNamespace

from aicl import claude


class FakeClient:
    """Records which endpoint was called and with what."""

    def __init__(self, stop="end_turn"):
        self.calls = []
        reply = SimpleNamespace(stop_reason=stop, stop_details=None,
                                content=[SimpleNamespace(type="text", text=" (T a.1>b true) ")])
        outer = self

        class Messages:
            def create(self, **kw):
                outer.calls.append(("messages", kw))
                return reply

        class BetaMessages:
            def create(self, **kw):
                outer.calls.append(("beta", kw))
                return reply

        self.messages = Messages()
        self.beta = SimpleNamespace(messages=BetaMessages())


class ClaudeAskTests(unittest.TestCase):
    def test_haiku_skips_server_side_fallbacks(self):
        fake = FakeClient()
        out = claude.text_ask(model="claude-haiku-5-5", client=fake)("SYS", [{"role": "user", "content": "x"}])
        self.assertEqual(out, "(T a.1>b true)")
        endpoint, kw = fake.calls[0]
        self.assertEqual(endpoint, "messages")
        self.assertNotIn("fallbacks", kw)
        self.assertEqual(kw["model"], "claude-haiku-5-5")
        self.assertEqual(kw["output_config"], {"effort": "low"})

    def test_opus_keeps_fallbacks(self):
        fake = FakeClient()
        claude.text_ask(client=fake)("SYS", [])
        endpoint, kw = fake.calls[0]
        self.assertEqual(endpoint, "beta")
        self.assertEqual(kw["fallbacks"], "default")
        self.assertEqual(kw["betas"], ["server-side-fallback-2026-07-01"])
        self.assertEqual(kw["max_tokens"], 16000)

    def test_truncated_answer_is_an_error(self):
        with self.assertRaises(RuntimeError):
            claude.text_ask(model="claude-haiku-5-5", client=FakeClient(stop="max_tokens"))("S", [])


if __name__ == "__main__":
    unittest.main()
