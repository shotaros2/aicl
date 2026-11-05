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

    def test_caching_is_on_and_usage_is_counted(self):
        fake = FakeClient()
        fake_usage = SimpleNamespace(input_tokens=100, output_tokens=50, cache_creation_input_tokens=4000,
                                     cache_read_input_tokens=0)
        orig = fake.messages.create

        def create(**kw):
            r = orig(**kw)
            r.usage = fake_usage
            return r
        fake.messages.create = create
        claude.USAGE.clear()
        try:
            claude.text_ask(model="claude-haiku-5-5", client=fake)("SYS", [])
            self.assertEqual(fake.calls[0][1]["cache_control"], {"type": "ephemeral"})
            u = claude.USAGE["claude-haiku-5-5"]
            self.assertEqual((u["calls"], u["input"], u["cache_write"], u["output"]), (1, 100, 4000, 50))
            # 100*0.10 + 4000*0.125 + 50*0.50 = 535 per million
            self.assertAlmostEqual(claude.cost_usd("claude-haiku-5-5", u), 0.000535)
            self.assertIn("about $0.0005", claude.usage_lines()[0])
        finally:
            claude.USAGE.clear()

    def test_truncated_answer_is_an_error(self):
        with self.assertRaises(RuntimeError):
            claude.text_ask(model="claude-haiku-5-5", client=FakeClient(stop="max_tokens"))("S", [])


if __name__ == "__main__":
    unittest.main()
