import threading
import unittest

from aicl.dialogue import AiclAgent
from aicl.relay import Relay, RelayClient, RelayReject, attend, make_server

try:
    from aicl.signing import generate_key, sign_form
    import aicl
    HAVE_CRYPTO = True
    try:
        generate_key()
    except Exception:
        HAVE_CRYPTO = False
except Exception:                                    # pragma: no cover
    HAVE_CRYPTO = False

import aicl  # noqa: E402  (re-import harmless)


def start(relay: Relay):
    srv = make_server(relay, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def scripted(*replies):
    it = iter(replies)
    return lambda system, history: next(it)


class RelayTests(unittest.TestCase):
    def test_post_poll_transcript_and_check(self):
        relay = Relay(known_terms=("temp",))
        srv, base = start(relay)
        try:
            a = RelayClient(base, "t1", "a")
            b = RelayClient(base, "t1", "b")
            a.send("(ask #a.1 @a>@b (temp tokyo $t))")
            self.assertEqual(b.poll(wait=2), ["(ask #a.1 @a>@b (temp tokyo $t))"])
            b.send("(T b.1>a ^a.1 {$t 18.5C} :s jma)")          # dense on the wire
            self.assertEqual(a.poll(wait=2), ["(tell #b.1 @b>@a ^a.1 {$t 18.5C} :src jma)"])
            self.assertEqual(b.poll(wait=0), [])                 # nothing new for @b
            a.send("(end #a.2 @a>@b)")
            self.assertIn("(ask #a.1", a.transcript())
            self.assertEqual(relay.check("t1"), "clean")
        finally:
            srv.shutdown()

    def test_invalid_message_is_rejected_not_delivered(self):
        srv, base = start(Relay())
        try:
            a = RelayClient(base, "t2", "a")
            b = RelayClient(base, "t2", "b")
            with self.assertRaises(RelayReject):
                a.send("this is not AICL")
            with self.assertRaises(RelayReject):                 # error-level issue: no :why on no
                a.send("(no #a.1 @a>@b ^b.9)")
            with self.assertRaises(RelayReject):
                a.send("(ask #a.1 @a>@b (x $v)) (ask #a.2 @a>@b (y $v))")   # two at once
            a.send("(ask #a.1 @a>@b (x $v))")
            with self.assertRaises(RelayReject):                 # duplicate id
                a.send("(ask #a.1 @a>@b (x $v))")
            self.assertEqual(len(b.poll(wait=0)), 1)
        finally:
            srv.shutdown()

    def test_attend_two_llm_agents_over_http(self):
        srv, base = start(Relay(known_terms=("temp",)))
        try:
            agent_a = AiclAgent("a", scripted("(ask #a.1 @a>@b (temp tokyo $t))", "(end #a.2 @a>@b)"), "sys")
            agent_b = AiclAgent("b", scripted("(tell #b.1 @b>@a ^a.1 {$t 18.5C} :src jma)"), "sys")
            tb = threading.Thread(target=attend,
                                  args=(RelayClient(base, "t3", "b"), agent_b),
                                  kwargs={"echo": None}, daemon=True)
            tb.start()
            attend(RelayClient(base, "t3", "a"), agent_a,
                   opening="; conversation start: send your first AICL message to @b", echo=None)
            tb.join(timeout=5)
            text = RelayClient(base, "t3", "a").transcript()
            self.assertEqual([line.split()[0].lstrip("(") for line in text.strip().splitlines()],
                             ["ask", "tell", "end"])
        finally:
            srv.shutdown()

    def test_rejection_is_bounced_back_to_the_llm(self):
        srv, base = start(Relay())
        try:
            agent_a = AiclAgent("a", scripted("not aicl at all", "(end #a.1 @a>@b)"), "sys")
            attend(RelayClient(base, "t4", "a"), agent_a, opening="; go", echo=None)
            self.assertIn("relay rejected", agent_a.history[2]["content"])
        finally:
            srv.shutdown()

    def test_relay_clock_is_served_and_prefixed(self):
        from datetime import datetime, timedelta, timezone
        fixed = datetime(2026, 11, 5, 21, 0, tzinfo=timezone(timedelta(hours=9)))
        srv, base = start(Relay(known_terms=("x",), now_fn=lambda: fixed))
        try:
            a = RelayClient(base, "t6", "a")
            a.poll(wait=0)
            self.assertEqual(a.now, "2026-11-05T21:00+09:00")
            agent_a = AiclAgent("a", scripted("(ask #a.1 @a>@b (x $v))", "(end #a.2 @a>@b)"), "sys")
            agent_b = AiclAgent("b", scripted("(tell #b.1 @b>@a ^a.1 {$v 1})"), "sys")
            tb = threading.Thread(target=attend, args=(RelayClient(base, "t7", "b"), agent_b),
                                  kwargs={"echo": None}, daemon=True)
            tb.start()
            attend(RelayClient(base, "t7", "a"), agent_a, opening="; go", echo=None)
            tb.join(timeout=5)
            self.assertTrue(agent_a.history[0]["content"].startswith("; now 2026-11-05T21:00+09:00"))
            self.assertTrue(agent_b.history[0]["content"].startswith("; now 2026-11-05T21:00+09:00"))
        finally:
            srv.shutdown()

    def test_at_skew_is_rejected_with_the_true_time(self):
        from datetime import datetime, timedelta, timezone
        fixed = datetime(2026, 11, 5, 21, 0, tzinfo=timezone(timedelta(hours=9)))
        srv, base = start(Relay(known_terms=("x",), now_fn=lambda: fixed))
        try:
            a = RelayClient(base, "t8", "a")
            with self.assertRaises(RelayReject) as cm:
                a.send("(do #a.1 @a>@b (x) :at 2026-11-04T09:00Z)")        # yesterday's fabrication
            self.assertIn("at-skew", cm.exception.issues[0])
            self.assertIn("2026-11-05T21:00+09:00", cm.exception.issues[0])  # the bounce teaches the time
            a.send("(do #a.1 @a>@b (x) :at 2026-11-05T20:58+09:00)")       # within tolerance
            a.send("(do #a.2 @a>@b (x))")                                  # no :at: allowed
        finally:
            srv.shutdown()

    def test_check_uses_the_relay_clock_for_deadlines(self):
        from datetime import datetime, timedelta, timezone
        fixed = datetime(2026, 11, 5, 21, 0, tzinfo=timezone(timedelta(hours=9)))
        relay = Relay(known_terms=("x",), now_fn=lambda: fixed)
        srv, base = start(relay)
        try:
            a = RelayClient(base, "t9", "a")
            a.send("(do #a.1 @a>@b (x) :by 2026-11-05T20:00+09:00)")       # deadline already past
            self.assertIn("deadline-passed", relay.check("t9"))
        finally:
            srv.shutdown()

    @unittest.skipUnless(HAVE_CRYPTO, "pip install aicl-lang[crypto]")
    def test_keys_enforced_at_the_door(self):
        priv, pub = generate_key()
        srv, base = start(Relay(known_terms=("x",), keys={"a": pub}))
        try:
            a = RelayClient(base, "t5", "a")
            with self.assertRaises(RelayReject):                 # unsigned from a bound agent
                a.send("(ask #a.1 @a>@b (x $v))")
            signed = aicl.to_text(sign_form(aicl.parse_one("(ask #a.1 @a>@b (x $v))"), priv))
            self.assertEqual(a.send(signed)["n"], 1)
            tampered = signed.replace("$v", "$w")
            with self.assertRaises(RelayReject):
                a.send(tampered.replace("#a.1", "#a.2"))
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
