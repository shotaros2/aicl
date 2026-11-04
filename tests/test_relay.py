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
