import io
import json
import os
import socket
import unittest
import urllib.error
from contextlib import contextmanager
from unittest import mock

from aicl import local, vendors
from aicl.network import Limits, ModelNode, Network
from aicl.night import TaskOutcome, write_report


def fake_opener(reply="(T b.1>a ^a.1 {$t 18.5C})", seen=None, fail=None):
    """Answers in Ollama's native /api/chat shape, or the OpenAI shape for /chat/completions."""
    @contextmanager
    def opener(req, timeout=0):
        if seen is not None:
            seen.append((req.full_url, json.loads(req.data.decode("utf-8")), timeout))
        if fail is not None:
            raise fail
        if req.full_url.endswith("/api/chat"):
            yield io.BytesIO(json.dumps({"message": {"role": "assistant", "content": reply}}).encode())
        else:
            yield io.BytesIO(json.dumps({"choices": [{"message": {"role": "assistant", "content": reply}}]}).encode())
    return opener


ENV_CLEAR = {"AICL_LOCAL_URL": "", "AICL_LOCAL_MODEL": "", "AICL_LOCAL_CTX": "", "AICL_LOCAL_API": "",
             "AICL_LOCAL_THINK": ""}


class LocalTests(unittest.TestCase):
    def test_defaults_point_at_ollama_native_with_a_larger_context(self):
        seen = []
        with mock.patch.dict(os.environ, ENV_CLEAR):
            ask = local.text_ask(opener=fake_opener(seen=seen))
            ask("SYS", [{"role": "user", "content": "hi"}])
        url, body, timeout = seen[0]
        self.assertEqual(url, "http://localhost:11434/api/chat")
        self.assertEqual(body["model"], "qwen3:8b")
        self.assertEqual(body["options"]["num_ctx"], 12288)   # Ollama's 4096 default cuts the rulebook off
        self.assertFalse(body["stream"])
        self.assertEqual(body["messages"][0], {"role": "system", "content": "SYS"})
        self.assertEqual(timeout, 300.0)

    def test_context_and_model_from_env(self):
        seen = []
        with mock.patch.dict(os.environ, dict(ENV_CLEAR, AICL_LOCAL_CTX="8192", AICL_LOCAL_MODEL="qwen3.5:9b")):
            local.text_ask(opener=fake_opener(seen=seen))("S", [])
            self.assertEqual(vendors.describe("local"), "local (qwen3.5:9b)")
        self.assertEqual(seen[0][1]["options"]["num_ctx"], 8192)
        self.assertEqual(seen[0][1]["model"], "qwen3.5:9b")

    def test_thinking_is_left_alone_unless_set(self):
        seen = []
        with mock.patch.dict(os.environ, ENV_CLEAR):
            local.text_ask(opener=fake_opener(seen=seen))("S", [])
            local.text_ask(opener=fake_opener(seen=seen), think=False)("S", [])
        with mock.patch.dict(os.environ, dict(ENV_CLEAR, AICL_LOCAL_THINK="false")):
            local.text_ask(opener=fake_opener(seen=seen))("S", [])
        with mock.patch.dict(os.environ, dict(ENV_CLEAR, AICL_LOCAL_THINK="on")):
            local.text_ask(opener=fake_opener(seen=seen))("S", [])
        self.assertNotIn("think", seen[0][1])
        self.assertEqual([s[1].get("think") for s in seen[1:]], [False, False, True])

    def test_openai_compatible_servers(self):
        seen = []
        with mock.patch.dict(os.environ, dict(ENV_CLEAR, AICL_LOCAL_URL="http://localhost:1234/v1",
                                              AICL_LOCAL_API="openai", AICL_LOCAL_MODEL="gemma3:12b")):
            local.text_ask(opener=fake_opener(seen=seen))("S", [])
        self.assertEqual(seen[0][0], "http://localhost:1234/v1/chat/completions")
        self.assertEqual(seen[0][1]["model"], "gemma3:12b")

    def test_thinking_is_removed(self):
        reply = "<think>the user wants a tell, so…</think>\n(T b.1>a ^a.1 {$t 18.5C})"
        with mock.patch.dict(os.environ, ENV_CLEAR):
            out = local.text_ask(opener=fake_opener(reply=reply))("S", [])
        self.assertEqual(out, "(T b.1>a ^a.1 {$t 18.5C})")
        self.assertEqual(local.strip_think("<think>never closed"), "")

    def test_server_down_counts_as_unavailable(self):
        refused = urllib.error.URLError(ConnectionRefusedError(10061, "refused"))
        for api in ("ollama", "openai"):
            with mock.patch.dict(os.environ, dict(ENV_CLEAR, AICL_LOCAL_API=api)):
                ask = local.text_ask(opener=fake_opener(fail=refused))
                with self.assertRaises(Exception) as cm:
                    ask("S", [])
            self.assertTrue(vendors.is_unavailable(cm.exception), api)


def scripted(name, replies, log):
    it = iter(replies)

    def ask(system, history):
        log.append(name)
        return next(it)
    return ask


class EscalationTests(unittest.TestCase):
    def make(self, local_replies, cloud_replies=("(T x.9>y true)",) * 5):
        log, notes = [], []
        ask = vendors.with_escalation("local", lambda: scripted("local", local_replies, log), "gemini",
                                      lambda: scripted("cloud", cloud_replies, log), note=notes.append)
        return ask, log, notes

    def test_two_invalid_in_a_row_escalates(self):
        ask, log, _ = self.make(["junk", "junk"])
        ask("S", []); self.assertFalse(ask.observe("invalid", "e1"))
        ask("S", []); self.assertTrue(ask.observe("invalid", "e2"))
        ask("S", [])
        self.assertEqual(log, ["local", "local", "cloud"])
        self.assertIn("2 invalid AICL answers in a row", ask.pending_notes()[0])
        self.assertEqual(ask.pending_notes(), [])          # drained once

    def test_a_valid_answer_resets_the_streak(self):
        ask, log, _ = self.make(["junk", "(T a.1>b true)", "junk", "(T a.2>b true)"])
        for kind in ("invalid", "valid", "invalid", "valid"):
            ask("S", []); ask.observe(kind)
        self.assertEqual(log, ["local"] * 4)
        self.assertEqual(ask.state["escalations"], [])

    def test_two_rejections_escalate(self):
        ask, log, _ = self.make(["(P a.1>c x)"] * 3)
        ask.observe("rejected", "#critic.1"); ask("S", [])
        ask.observe("rejected", "#critic.2"); ask("S", [])
        self.assertEqual(log, ["local", "cloud"])

    def test_server_down_escalates_and_the_turn_is_answered(self):
        def down():
            def ask(system, history):
                raise urllib.error.URLError(ConnectionRefusedError(10061, "refused"))
            return ask
        log, notes = [], []
        ask = vendors.with_escalation("local", down, "gemini", lambda: scripted("cloud", ["(T a.1>b true)"], log),
                                      note=notes.append)
        self.assertEqual(ask("S", []), "(T a.1>b true)")
        self.assertIn("unavailable or stalled", ask.state["escalations"][0])

    def test_timeout_escalates(self):
        def slow():
            def ask(system, history):
                raise socket.timeout("timed out")
            return ask
        ask = vendors.with_escalation("local", slow, "gemini", lambda: (lambda s, h: "(T a.1>b true)"),
                                      note=lambda s: None)
        self.assertEqual(ask("S", []), "(T a.1>b true)")

    def test_a_slow_empty_answer_is_answered_by_the_cloud_at_once(self):
        log = []
        ticks = iter([0.0, 500.0])
        with mock.patch.object(vendors.time, "monotonic", lambda: next(ticks)):
            ask = vendors.with_escalation("local", lambda: scripted("local", [""], log), "gemini",
                                          lambda: scripted("cloud", ["(K a.1>b ^b.1)"], log), note=lambda s: None)
            self.assertEqual(ask("S", []), "(K a.1>b ^b.1)")
        self.assertEqual(log, ["local", "cloud"])
        self.assertIn("and it was empty", ask.state["escalations"][0])

    def test_a_slow_answer_with_content_is_kept(self):
        log = []
        ticks = iter([0.0, 500.0])
        with mock.patch.object(vendors.time, "monotonic", lambda: next(ticks)):
            ask = vendors.with_escalation("local", lambda: scripted("local", ["(K a.1>b ^b.1)"], log), "gemini",
                                          lambda: scripted("cloud", ["x"], log), note=lambda s: None)
            self.assertEqual(ask("S", []), "(K a.1>b ^b.1)")
        self.assertEqual(log, ["local"])

    def test_a_bad_answer_is_not_a_reason_to_switch(self):
        def broken():
            def ask(system, history):
                raise ValueError("model produced garbage")
            return ask
        ask = vendors.with_escalation("local", broken, "gemini", lambda: (lambda s, h: ""), note=lambda s: None)
        with self.assertRaises(ValueError):
            ask("S", [])

    def test_escalation_target_model_is_used_and_named(self):
        calls, notes = [], []

        def fake_api(vendor, model, sleep):
            calls.append((vendor, model))
            if vendor == "local":
                return lambda s, h: "junk"
            return lambda s, h: "(T a.1>b true)"
        with mock.patch.object(vendors, "_api_ask", fake_api):
            ask = vendors.text_ask("local", escalate_to="claude", escalate_model="claude-haiku-5-5",
                                   note=notes.append)
            ask("S", []); ask.observe("invalid", "e1")
            ask("S", []); ask.observe("invalid", "e2")
            self.assertEqual(ask("S", []), "(T a.1>b true)")
        self.assertIn(("claude", "claude-haiku-5-5"), calls)
        self.assertIn("escalated to claude (claude-haiku-5-5)", notes[0])

    def test_text_ask_wiring(self):
        with self.assertRaises(ValueError):
            vendors.text_ask("local", escalate_to="local")
        ask = vendors.text_ask("local", escalate_to="gemini", note=lambda s: None)
        self.assertTrue(hasattr(ask, "observe"))


class ReadableInputTests(unittest.TestCase):
    """A local model mirrors the dense header (user.1>local) into `local.1>user.1`; the readable
    form gives it nothing to mirror. The option only changes what the model is shown."""

    def run_one(self, readable):
        import aicl
        from aicl.network import Node
        seen = []

        def ask(system, history):
            seen.append(history[-1]["content"])
            return "(no #local.1 @local>@user ^user.1 :why (unk data))"
        owner = Node("user", "the person")
        agent = ModelNode("local", "answer", ask, "rulebook for me", readable_input=readable)
        net = Network([owner, agent], Limits(max_messages=5), sign=False, echo=None)
        net.post(owner.msg("ask", "local", aicl.parse_one("(x $v)")))
        res = net.run(wake=[])
        return seen[0], res

    def test_readable_input_shows_the_canonical_header(self):
        shown, res = self.run_one(True)
        self.assertIn("(ask #user.1 @user>@local (x $v))", shown)
        self.assertNotIn("user.1>local", shown)
        self.assertEqual([m.act for m in res.messages], ["ask", "no"])

    def test_default_stays_dense(self):
        shown, _ = self.run_one(False)
        self.assertIn("(A user.1>local (x $v))", shown)


class EmptyRetryTests(unittest.TestCase):
    def test_an_empty_resend_counts_as_invalid_and_the_cloud_finishes(self):
        log = []
        ask = vendors.with_escalation("local", lambda: scripted("local", ["(T chief.1>owner ^owner.1 {$x 1", ""], log),
                                      "gemini", lambda: scripted("cloud", ["(T chief.1>owner ^owner.1 {$x 1})"], log),
                                      note=lambda s: None)
        from aicl.network import Node
        owner = Node("owner", "the person")
        chief = ModelNode("chief", "lead", ask, "rulebook for me")
        net = Network([owner, chief], Limits(max_messages=10, max_calls_per_agent=5), sign=False, echo=None)
        net.post(owner.msg("ask", "chief", __import__("aicl").parse_one("(x $x)")))
        res = net.run(wake=[])
        self.assertEqual(log, ["local", "local", "cloud"])
        self.assertEqual([m.act for m in res.messages], ["ask", "tell"])
        self.assertTrue(any("empty answer" in n for n in res.notes))


class NetworkEscalationTests(unittest.TestCase):
    """End to end inside the network: the local chief answers junk twice, the role moves to the
    cloud, the cloud gets a fresh try at the same event, and the report says so."""

    def test_network_escalates_and_report_shows_it(self):
        log = []
        local_replies = ["not aicl", "still not aicl"]
        cloud_replies = ["(T chief.1>owner ^owner.1 {$x 1})"]
        ask = vendors.with_escalation("local", lambda: scripted("local", local_replies, log), "gemini",
                                      lambda: scripted("cloud", cloud_replies, log), note=lambda s: None)
        from aicl.network import Node
        owner = Node("owner", "the person")
        chief = ModelNode("chief", "lead", ask, "rulebook for me")
        net = Network([owner, chief], Limits(max_messages=10, max_calls_per_agent=5), sign=False, echo=None)
        net.post(owner.msg("ask", "chief", __import__("aicl").parse_one("(x $x)")))
        res = net.run(wake=[])
        self.assertEqual(log, ["local", "local", "cloud"])
        self.assertEqual([m.act for m in res.messages], ["ask", "tell"])
        ups = [n for n in res.notes if "escalated to gemini" in n]
        self.assertEqual(len(ups), 1)
        self.assertTrue(ups[0].startswith("@chief "))

        import tempfile
        from datetime import datetime
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            out = TaskOutcome("t1", "テスト", "done", None, res, False, "", [])
            text = write_report(Path(d), [out], datetime.now()).read_text(encoding="utf-8")
        self.assertIn("手元の AI からクラウドに上げた回数: 1 件", text)
        self.assertIn("不正な返答: 2 件", text)          # the two junk answers, not the escalation note


if __name__ == "__main__":
    unittest.main()
