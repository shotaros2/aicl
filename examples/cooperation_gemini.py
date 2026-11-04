"""Specialists cooperating in AICL, with Gemini in three roles.

- The hub's planner is Gemini (LLMPlanner): it writes the (coop:plan ...) in AICL.
- The image specialist calls a Gemini image model and returns a coop:artifact
  with the saved PNG (SkillAgent: the model generates pixels, not AICL).
- The code specialist IS Gemini speaking AICL (LLMAgent): it receives the task
  as a dense AICL message and must answer with (K ...) and (Z ... (coop:artifact ...)).

Every message is validated on the bus; the transcript is written to out/.

Needs:  pip install google-genai   and   GEMINI_API_KEY
Run:    python examples/cooperation_gemini.py [--text-model NAME] [--image-model NAME] [--goal "..."]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import aicl
from aicl import tokens
from aicl.build import form, nl
from aicl.coop import Agent, Bus, Hub, LLMAgent, LLMPlanner, SkillAgent
from aicl.env import load_dotenv

load_dotenv()

OUT = ROOT / "out"
RULEBOOK = (ROOT / "prompts" / "system_prompt_dense.md").read_text(encoding="utf-8").split("---", 1)[1].strip()
COOP = (ROOT / "schemas" / "cooperation.md").read_text(encoding="utf-8")


# ------------------------------------------------------------------ gemini calls

def with_retry(fn, attempts=5, wait=5.0, what=""):
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            msg = str(e)
            if "PerDay" in msg or "per day" in msg:
                sys.exit(f"daily free-tier quota exhausted for {what or 'this model'}; "
                         "pick another with evals/readback.py --list-models (--text-model / --image-model)")
            if i == attempts - 1 or not any(k in msg for k in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                raise
            print(f"  transient error, retrying in {wait:.0f}s: {msg[:80]}", file=sys.stderr)
            time.sleep(wait)
            wait = min(wait * 2, 60)


def make_client():
    from google import genai
    return genai.Client()


def text_call(client, model, sleep):
    from google.genai import types

    def ask(system: str, history: list[dict]) -> str:
        contents = [types.Content(role="user" if h["role"] == "user" else "model",
                                  parts=[types.Part.from_text(text=h["content"])]) for h in history]
        cfg = types.GenerateContentConfig(system_instruction=system, temperature=0)
        resp = with_retry(lambda: client.models.generate_content(model=model, contents=contents, config=cfg), what=f"text model {model}")
        time.sleep(sleep)
        return resp.text or ""
    return ask


def image_call(client, model, sleep):
    from google.genai import types

    def generate(inputs: dict, task_id: str) -> dict:
        prompt = inputs["prompt"].text if isinstance(inputs.get("prompt"), aicl.Str) else aicl.to_text(inputs.get("prompt"))
        cfg = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
        resp = with_retry(lambda: client.models.generate_content(model=model, contents=prompt, config=cfg), what=f"image model {model}")
        time.sleep(sleep)
        for part in resp.candidates[0].content.parts:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                OUT.mkdir(exist_ok=True)
                ext = "png" if "png" in part.inline_data.mime_type else "jpg"
                path = OUT / f"{task_id}.{ext}"
                path.write_bytes(part.inline_data.data)
                return {"id": f"img-{task_id}", "type": "image", "uri": path.resolve().as_uri(),
                        "mime": part.inline_data.mime_type}
        raise RuntimeError("image model returned no image")
    return generate


def svg_image_call(ask, sleep):
    """Free-tier fallback: the text model draws the image as SVG (--image-model svg)."""
    import re

    def generate(inputs: dict, task_id: str) -> dict:
        prompt = inputs["prompt"].text if isinstance(inputs.get("prompt"), aicl.Str) else aicl.to_text(inputs.get("prompt"))
        raw = ask("You are an illustrator. Answer with one complete <svg …>…</svg> element (viewBox 0 0 1920 1080, "
                  "no external references, no scripts) and nothing else.",
                  [{"role": "user", "content": f"Draw: {prompt}"}])
        m = re.search(r"<svg.*?</svg>", raw, re.S)
        if not m:
            raise RuntimeError("text model returned no <svg> element")
        OUT.mkdir(exist_ok=True)
        path = OUT / f"{task_id}.svg"
        path.write_text(m.group(0), encoding="utf-8")
        return {"id": f"img-{task_id}", "type": "image", "uri": path.resolve().as_uri(), "mime": "image/svg+xml"}
    return generate


CODE_ROLE = """Your role: you are @code, a specialist with the skill code-gen, cooperating through a hub.
The cooperation vocabulary (coop: namespace) is documented below. When you receive
(D hub.N>code (coop:task <tid> code-gen :in {embed <coop:artifact ...> title "..."}))
answer with exactly two AICL messages on two lines, nothing else:
(K code.<n>>hub ^hub.N)
(Z code.<n+1>>hub ^hub.N (coop:artifact page-<tid> :type code :task <tid> :mime "text/html" :content "<html>"))
The HTML must be one line, use single quotes inside it, and embed the artifact's :uri in an <img> tag
with the title as the page <title> and <h1>. If the task is not code-gen, answer (N code.<n>>hub ^hub.N :w (unk <skill>)).

""" + COOP


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--text-model", default="gemini-3.5-flash-lite")
    ap.add_argument("--image-model", default="gemini-nano-banana-2.1",
                    help="a Gemini image model, or 'svg' to have the text model draw an SVG (works on the free tier)")
    ap.add_argument("--goal", default="東京の夜景の画像を作って、それを埋め込んだWebページを作って")
    ap.add_argument("--sleep", type=float, default=4.0, help="seconds between calls (free-tier rate limits)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    client = make_client()
    ask = text_call(client, a.text_model, a.sleep)

    bus = Bus()
    hub = Hub(LLMPlanner(lambda prompt: ask("You answer with exactly one AICL form and nothing else.",
                                            [{"role": "user", "content": prompt}])))
    image_fn = svg_image_call(ask, a.sleep) if a.image_model == "svg" else image_call(client, a.image_model, a.sleep)
    img = SkillAgent("img", "image-gen", image_fn)
    code = LLMAgent("code", ask, RULEBOOK, CODE_ROLE, capabilities=["code-gen"])
    user = Agent("user")
    bus.add(hub, img, code, user)
    for s in (img, code):
        for f in s.announce("hub"):
            bus.send(f)

    print(f"hub planner: {a.text_model} | image-gen: {a.image_model} | code-gen: {a.text_model} speaking AICL\n")
    bus.send(user.msg("do", "hub", form("coop:goal", nl("ja", a.goal))))

    print("--- transcript (readable) ---")
    print(bus.text())
    issues = bus.check()
    errors = [i for i in issues if i.level == "error"]
    print("\n--- protocol check ---")
    for i in issues:
        print(" ", i)
    final = bus.transcript[-1]
    print(f"{len(bus.transcript)} messages, {len(errors)} errors, nl ratio {aicl.nl_ratio(bus.transcript):.1%}, "
          f"{tokens.count(bus.text())} tokens ({tokens.METHOD}); final: {final.act} -> @{final.receiver}")
    OUT.mkdir(exist_ok=True)
    (OUT / "transcript.aicl").write_text(bus.text() + "\n", encoding="utf-8")
    if final.act == "done" and final.receiver == "user":
        for art in final.body[0].items:
            kw = art.kw
            if "content" in kw:
                page = OUT / "page.html"
                page.write_text(kw["content"].text, encoding="utf-8")
                print(f"wrote {page}")
            elif "uri" in kw:
                print(f"artifact {art.args[0].name}: {kw['uri'].text}")
    print(f"transcript: {OUT / 'transcript.aicl'}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
