import io
import json
import os
import tempfile
import unittest
import urllib.error
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from aicl.discordlink import Link


class FakeDiscord:
    """Records every request; answers GET /channels/<tasks>/messages from a scripted list."""

    def __init__(self, messages=(), fail=False):
        self.messages = list(messages)
        self.calls = []
        self.fail = fail

    def __call__(self, req, timeout=0):
        @contextmanager
        def cm():
            self.calls.append((req.get_method(), req.full_url, dict(req.header_items()), req.data))
            if self.fail:
                raise urllib.error.HTTPError(req.full_url, 403, "no", {}, io.BytesIO(b'{"message":"Missing Access"}'))
            body = b""
            if req.get_method() == "GET" and "/messages" in req.full_url:
                after = req.full_url.split("after=")[1] if "after=" in req.full_url else None
                rows = [m for m in self.messages if after is None or int(m["id"]) > int(after)]
                body = json.dumps(rows).encode()
            elif req.get_method() == "GET":
                body = json.dumps({"username": "aicl-house", "name": "tasks"}).encode()
            yield io.BytesIO(body)
        return cm()


def link(fake, tmp, **kw):
    return Link("HOUSE", "42", "100", "200", state_path=Path(tmp) / "state.json", note=lambda s: None,
                opener=fake, pause=0, **kw)


OWNER = {"id": "42", "bot": False}


class DiscordTests(unittest.TestCase):
    def test_only_the_owners_new_messages_become_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeDiscord([{"id": "1", "author": OWNER, "content": "古い依頼"}])
            l, inbox = link(fake, tmp), Path(tmp) / "inbox"
            self.assertEqual(l.pull_tasks(inbox), 0)                 # first run starts from now
            fake.messages += [{"id": "2", "author": OWNER, "content": "スカイツリーをまとめて"},
                              {"id": "3", "author": {"id": "77"}, "content": "私の仕事もやって"},
                              {"id": "4", "author": {"id": "9", "bot": True}, "content": "(D x.1>chief …)"},
                              {"id": "5", "author": OWNER, "content": ""}]
            self.assertEqual(l.pull_tasks(inbox), 1)
            self.assertEqual([p.name for p in inbox.glob("*.txt")], ["discord-2.txt"])
            self.assertIn("スカイツリー", (inbox / "discord-2.txt").read_text(encoding="utf-8"))
            self.assertTrue(any(m == "PUT" and "/messages/2/reactions/" in u for m, u, h, d in fake.calls))
            self.assertEqual(l.pull_tasks(inbox), 0)                 # nothing is taken twice
            self.assertEqual(json.loads((Path(tmp) / "state.json").read_text())["after"], "5")

    def test_an_empty_channel_still_starts_from_now(self):
        import time
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeDiscord([])
            l, inbox = link(fake, tmp), Path(tmp) / "inbox"
            self.assertEqual(l.pull_tasks(inbox), 0)
            start = int(json.loads((Path(tmp) / "state.json").read_text())["after"])
            now_id = (int(time.time() * 1000) - 1420070400000) << 22
            self.assertLess(abs(now_id - start), 60_000 << 22)      # within a minute of now
            fake.messages.append({"id": str(now_id + (5_000 << 22)), "author": OWNER, "content": "最初の依頼"})
            self.assertEqual(l.pull_tasks(inbox), 1)                 # the first task is not taken for history

    def test_each_agent_speaks_under_its_own_account_or_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeDiscord()
            l = link(fake, tmp, wire_webhook="https://discord.com/api/webhooks/1/x", wire_channel="300",
                     agent_tokens={"CHIEF": "CHIEF-TOKEN"})
            l.mirror("chief", "(A chief.1>fx (fx-rate USD JPY $r))")
            l.mirror("critic", "(C critic.1>chief ^chief.2)" + " " * 3000)
            (m1, u1, h1, d1), (m2, u2, h2, d2) = fake.calls
            self.assertEqual((m1, u1, h1["Authorization"]), ("POST", "https://discord.com/api/v10/channels/300/messages",
                                                             "Bot CHIEF-TOKEN"))
            self.assertTrue(u2.startswith("https://discord.com/api/webhooks/1/x?wait=true"))
            body = json.loads(d2)
            self.assertEqual(body["username"], "@critic")
            self.assertLessEqual(len(body["content"]), 2000)
            self.assertNotIn("Authorization", h2)                   # a webhook needs no token

    def test_reports_go_out_as_files_and_errors_never_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "REPORT.md"
            report.write_text("# 夜間作業の報告\n完了 1 件", encoding="utf-8")
            page = Path(tmp) / "page.md"
            page.write_text("# 為替", encoding="utf-8")
            fake = FakeDiscord()
            link(fake, tmp).post_report(report, [page])
            method, url, headers, data = fake.calls[0]
            self.assertTrue(url.endswith("/channels/200/messages"))
            self.assertIn("multipart/form-data", headers["Content-type"])
            self.assertIn(b'filename="REPORT.md"', data)
            self.assertIn(b'filename="page.md"', data)
            notes = []
            broken = Link("HOUSE", "42", "100", "200", note=notes.append, opener=FakeDiscord(fail=True), pause=0)
            broken.post_report(report)
            self.assertEqual(broken.pull_tasks(Path(tmp) / "inbox"), 0)
            broken.mirror("chief", "(T chief.1>x true)")             # no wire configured: silently nothing
            self.assertEqual(len(notes), 2)
            self.assertTrue(all("403" in n for n in notes))
            self.assertNotIn("HOUSE", " ".join(notes))               # the token never reaches a log line

    def test_without_a_webhook_the_house_bot_posts_with_the_agents_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeDiscord()
            link(fake, tmp, wire_channel="300").mirror("scout", "(A scout.1>news (headlines $h))")
            method, url, headers, data = fake.calls[0]
            self.assertTrue(url.endswith("/channels/300/messages"))
            self.assertEqual(headers["Authorization"], "Bot HOUSE")
            self.assertTrue(json.loads(data)["content"].startswith("**@scout**"))
        env = {"DISCORD_BOT_TOKEN": "T", "DISCORD_OWNER_ID": "1", "DISCORD_TASKS_CHANNEL": "2",
               "DISCORD_REPORTS_CHANNEL": "3", "DISCORD_WIRE_WEBHOOK": "1567788048287010866"}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch("aicl.discordlink.load_dotenv", lambda: 0):
            l = Link.from_env()
        self.assertEqual((l.wire_webhook, l.wire_channel), ("", "1567788048287010866"))   # a channel id, not a URL

    def test_discord_is_optional(self):
        with mock.patch.dict(os.environ, {"DISCORD_BOT_TOKEN": ""}, clear=False), \
             mock.patch("aicl.discordlink.load_dotenv", lambda: 0):
            self.assertIsNone(Link.from_env())

    def test_the_network_shows_every_message_to_an_observer(self):
        from aicl.network import ModelNode, Network
        seen = []
        n = ModelNode("a", "r", lambda s, h: "(T a.1>b true)" if "; wake" in h[-1]["content"] else "", "id `me`")
        b = ModelNode("b", "r", lambda s, h: "", "id `me`")
        Network([n, b], sign=False, echo=None, on_message=lambda m: seen.append((m.sender, m.act))).run()
        self.assertEqual(seen, [("a", "tell")])


if __name__ == "__main__":
    unittest.main()
