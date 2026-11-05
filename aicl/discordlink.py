"""Discord link: give the AI team Discord accounts, take tasks from Discord, post results to Discord.

- Tasks in: every message YOU write in the tasks channel becomes a task file in the night shift's
  inbox (messages from anyone else, and from bots, are ignored - strangers cannot give the team work).
  The bot answers with a reaction so you see it was taken.
- The AIs speak in Discord: each AICL message the network delivers is posted to the wire channel under
  the sending agent's own name - with that agent's own bot account when you created one for it
  (DISCORD_TOKEN_CHIEF, …), otherwise through one webhook that shows the agent's name.
- Reports out: the morning report and the published pages are posted to the reports channel as files.

The conversation itself still runs on the PC through aicl.network - signed, clocked and validated - and
Discord shows it; Discord is the team's room and mailbox, not where the thinking happens.
Discord never breaks a shift: every Discord error is noted and the work goes on.

Configuration lives in .env (never in chat):
  DISCORD_BOT_TOKEN        the house bot (reads tasks, posts reports)              required
  DISCORD_OWNER_ID         your Discord user id: only your messages become tasks    required
  DISCORD_TASKS_CHANNEL    channel id where you write tasks                         required
  DISCORD_REPORTS_CHANNEL  channel id for reports                                   required
  DISCORD_WIRE_WEBHOOK     webhook URL of the channel where the AIs talk            optional
  DISCORD_WIRE_CHANNEL     that channel's id, for agents with their own bot          optional
  DISCORD_TOKEN_<AGENT>    an agent's own bot account, e.g. DISCORD_TOKEN_CHIEF      optional
Check the setup without running anything:  python -m aicl.discordlink check
Standard library only.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import tls
from .env import load_dotenv

API = "https://discord.com/api/v10"
UA = "DiscordBot (https://github.com/shotaros2/aicl, 0.3)"
LIMIT = 1900                         # Discord allows 2000 characters per message


class DiscordError(RuntimeError):
    pass


def http(method: str, url: str, token: Optional[str] = None, payload=None, files: List[Path] = (),
         opener=None) -> object:
    """One Discord REST call; waits and retries on a 429. Returns the decoded JSON (or None)."""
    headers = {"User-Agent": UA}
    if token:
        headers["Authorization"] = f"Bot {token}"
    data = None
    if files:
        boundary = uuid.uuid4().hex
        parts = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\n"
                 f"Content-Type: application/json\r\n\r\n{json.dumps(payload or {})}\r\n".encode("utf-8")]
        for i, f in enumerate(files):
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"files[{i}]\"; filename=\"{f.name}\"\r\n"
                         f"Content-Type: application/octet-stream\r\n\r\n".encode("utf-8") + Path(f).read_bytes() + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        data = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    opener = opener or tls.urlopen
    for attempt in range(4):
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with opener(req, timeout=30) as r:
                body = r.read()
                return json.loads(body.decode("utf-8")) if body else None
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            if e.code == 429 and attempt < 3:
                try:
                    wait = float(json.loads(detail).get("retry_after", 1.0))
                except ValueError:
                    wait = 1.0
                time.sleep(min(wait, 10.0) + 0.2)
                continue
            raise DiscordError(f"{method} {url.split('?')[0].replace(API, '')} -> {e.code}: {detail[:200]}") from None
    raise DiscordError("rate limited")


class Link:
    """The team's Discord presence. Build it with Link.from_env(); every method is safe to call."""

    def __init__(self, token: str, owner_id: str, tasks_channel: str, reports_channel: str,
                 wire_webhook: str = "", wire_channel: str = "", agent_tokens: Dict[str, str] = None,
                 state_path: Path = None, note: Callable[[str], None] = print, opener=None, pause: float = 0.4):
        self.token, self.owner_id = token, str(owner_id)
        self.tasks_channel, self.reports_channel = str(tasks_channel), str(reports_channel)
        self.wire_webhook, self.wire_channel = wire_webhook, str(wire_channel or "")
        self.agent_tokens = {k.lower(): v for k, v in (agent_tokens or {}).items()}
        self.state_path = Path(state_path) if state_path else None
        self.note, self.opener, self.pause = note, opener, pause

    @classmethod
    def from_env(cls, state_path: Path = None, note: Callable[[str], None] = print) -> Optional["Link"]:
        """A Link when the required settings are in the environment or .env, else None (Discord is optional)."""
        load_dotenv()
        e = os.environ
        need = ("DISCORD_BOT_TOKEN", "DISCORD_OWNER_ID", "DISCORD_TASKS_CHANNEL", "DISCORD_REPORTS_CHANNEL")
        if not all(e.get(k) for k in need):
            return None
        agents = {k[len("DISCORD_TOKEN_"):]: v for k, v in e.items() if k.startswith("DISCORD_TOKEN_") and v}
        webhook, wire = e.get("DISCORD_WIRE_WEBHOOK", "").strip(), e.get("DISCORD_WIRE_CHANNEL", "").strip()
        if webhook.isdigit():               # a channel id put where the webhook goes: use it as the wire channel
            webhook, wire = "", wire or webhook
        return cls(e["DISCORD_BOT_TOKEN"], e["DISCORD_OWNER_ID"], e["DISCORD_TASKS_CHANNEL"],
                   e["DISCORD_REPORTS_CHANNEL"], webhook, wire, agents, state_path, note)

    def _call(self, method, path, token=None, payload=None, files=(), auth=True):
        return http(method, path if path.startswith("http") else API + path, (token or self.token) if auth else None,
                    payload, files, self.opener)

    # ------------------------------------------------------------ tasks in
    def _state(self) -> dict:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path else {}
        except (OSError, ValueError):
            return {}

    def _save(self, state: dict) -> None:
        if self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(state), encoding="utf-8")

    def pull_tasks(self, inbox: Path) -> int:
        """Turn new messages from the owner in the tasks channel into inbox files. Returns how many."""
        try:
            state = self._state()
            after = state.get("after")
            path = f"/channels/{self.tasks_channel}/messages?limit=50" + (f"&after={after}" if after else "")
            msgs = sorted(self._call("GET", path) or [], key=lambda m: int(m["id"]))
            if after is None:                     # first run: start from now, do not replay old history
                # An empty channel has no last id: use a Discord id made from the current time instead,
                # so the first task written after this moment is not mistaken for history.
                state["after"] = msgs[-1]["id"] if msgs else str((int(time.time() * 1000) - 1420070400000) << 22)
                self._save(state)
                return 0
            n = 0
            inbox.mkdir(parents=True, exist_ok=True)
            for m in msgs:
                state["after"] = m["id"]
                author = m.get("author", {})
                text = (m.get("content") or "").strip()
                if author.get("bot") or str(author.get("id")) != self.owner_id or not text:
                    continue
                (inbox / f"discord-{m['id']}.txt").write_text(text + "\n", encoding="utf-8")
                n += 1
                try:
                    self._call("PUT", f"/channels/{self.tasks_channel}/messages/{m['id']}/reactions/%F0%9F%93%A5/@me")
                except DiscordError:
                    pass
            self._save(state)
            return n
        except Exception as e:
            self.note(f"! discord: could not read tasks ({str(e)[:160]})")
            return 0

    # ----------------------------------------------------------- AIs speak
    def mirror(self, sender: str, text: str) -> None:
        """Post one AICL message under its sender's name (own bot account if there is one)."""
        body = text if len(text) <= LIMIT - 10 else text[:LIMIT - 40] + " …(続きは記録に)"
        content = f"```lisp\n{body}\n```"
        try:
            token = self.agent_tokens.get(sender.lower())
            if token and self.wire_channel:
                self._call("POST", f"/channels/{self.wire_channel}/messages", token, {"content": content})
            elif self.wire_webhook:
                if not self.wire_webhook.startswith(("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")):
                    raise DiscordError("DISCORD_WIRE_WEBHOOK is not a discord.com webhook URL")
                # A webhook URL carries its own secret: the bot token is never sent along.
                self._call("POST", self.wire_webhook + ("&" if "?" in self.wire_webhook else "?") + "wait=true",
                           None, {"content": content, "username": f"@{sender}"[:80]}, auth=False)
            elif self.wire_channel:          # no webhook: the house bot posts, with the agent's name up front
                self._call("POST", f"/channels/{self.wire_channel}/messages", None,
                           {"content": f"**@{sender}**\n{content}"[:2000]})
            else:
                return
            if self.pause:
                time.sleep(self.pause)
        except Exception as e:
            self.note(f"! discord: could not post @{sender}'s message ({str(e)[:120]})")

    # --------------------------------------------------------- reports out
    def post_report(self, report: Path, attachments: List[Path] = ()) -> None:
        try:
            text = Path(report).read_text(encoding="utf-8")
            head = text if len(text) <= LIMIT else text[:LIMIT - 30] + "\n…(全文は添付)"
            files = [Path(report)] + [Path(a) for a in attachments if Path(a).is_file()][:9]
            self._call("POST", f"/channels/{self.reports_channel}/messages", None, {"content": head}, files)
        except Exception as e:
            self.note(f"! discord: could not post the report ({str(e)[:160]})")

    def say(self, text: str) -> None:
        try:
            self._call("POST", f"/channels/{self.reports_channel}/messages", None, {"content": text[:LIMIT]})
        except Exception as e:
            self.note(f"! discord: could not post ({str(e)[:160]})")

    # ---------------------------------------------------------------- check
    def check(self) -> List[str]:
        """Human-readable lines saying what works, without printing any secret."""
        out = []
        try:
            me = self._call("GET", "/users/@me")
            out.append(f"ok   house bot signed in as {me.get('username')}")
        except Exception as e:
            return [f"FAIL house bot token: {e}"]
        for label, ch in (("tasks", self.tasks_channel), ("reports", self.reports_channel)):
            try:
                c = self._call("GET", f"/channels/{ch}")
                out.append(f"ok   {label} channel #{c.get('name')}")
            except Exception as e:
                out.append(f"FAIL {label} channel {ch}: {e}")
        try:
            msgs = self._call("GET", f"/channels/{self.tasks_channel}/messages?limit=5") or []
            mine = [m for m in msgs if str(m.get("author", {}).get("id")) == self.owner_id]
            if mine and not any(m.get("content") for m in mine):
                out.append("WARN your messages arrive empty: turn on MESSAGE CONTENT INTENT for the bot")
            else:
                out.append("ok   can read the tasks channel")
        except Exception as e:
            out.append(f"FAIL reading tasks: {e}")
        if self.wire_webhook:
            out.append("ok   wire webhook set: each AI posts under its own name")
        elif self.wire_channel:
            try:
                c = self._call("GET", f"/channels/{self.wire_channel}")
                out.append(f"ok   wire channel #{c.get('name')}: the house bot posts each AI's messages with its name")
            except Exception as e:
                out.append(f"FAIL wire channel {self.wire_channel}: {e}")
        else:
            out.append("--   no wire channel or webhook: the AIs' messages will not be shown")
        for agent, tok in sorted(self.agent_tokens.items()):
            try:
                me = self._call("GET", "/users/@me", tok)
                out.append(f"ok   @{agent} has its own bot account: {me.get('username')}"
                           + ("" if self.wire_channel else " (set DISCORD_WIRE_CHANNEL so it can post)"))
            except Exception as e:
                out.append(f"FAIL @{agent}'s token: {e}")
        return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    link = Link.from_env()
    if link is None:
        print("Discord is not configured: set DISCORD_BOT_TOKEN, DISCORD_OWNER_ID, DISCORD_TASKS_CHANNEL and "
              "DISCORD_REPORTS_CHANNEL in .env (see .env.example)")
        return 1
    if argv[:1] == ["check"]:
        for line in link.check():
            print(line)
        return 0
    if argv[:1] == ["hello"]:
        link.say("AICL チームが Discord につながりました。#タスク に書いたことを夜のうちにこなします。")
        for agent in ("chief", "writer", "critic", "scout"):
            link.mirror(agent, f"(T {agent}.0>* (online @{agent}))")
        print("posted a greeting")
        return 0
    print("usage: python -m aicl.discordlink check | hello")
    return 1


if __name__ == "__main__":
    sys.exit(main())
