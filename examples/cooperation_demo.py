"""Specialists with different strengths cooperating in AICL, offline.

An image-generation agent, a video-generation agent and a code-generation agent
register with a hub. A user sends one goal in Japanese (quarantined in `nl`); the
hub plans three dependent tasks, delegates them in order, passes each artifact
to the next specialist, and returns all artifacts to the user. Every message on
the bus is validated AICL. The specialists are stubs here; replace their
functions with real API calls (or use LLMAgent) and nothing else changes.

Run:  python examples/cooperation_demo.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aicl
from aicl import tokens
from aicl.build import form, msg, nl
from aicl.coop import Bus, Hub, RecipePlanner, SkillAgent, TaskRef, TaskSpec
from aicl.model import Quantity, Str


# ---------------------------------------------------------------- specialists (stubs)

def image_gen(inputs, task_id):
    prompt = inputs["prompt"].text
    name = f"img-{hashlib.sha1(prompt.encode()).hexdigest()[:6]}"
    return {"id": name, "type": "image", "uri": f"file://out/{name}.png", "mime": "image/png"}


def video_gen(inputs, task_id):
    keyframe = inputs["keyframe"]                       # the coop:artifact form from the image agent
    if not (isinstance(keyframe, aicl.Form) and keyframe.head == "coop:artifact"):
        raise ValueError("keyframe must be a coop:artifact")
    seconds = inputs["duration"].value
    name = f"vid-{keyframe.args[0].name}-{seconds}s"
    return {"id": name, "type": "video", "uri": f"file://out/{name}.mp4", "mime": "video/mp4"}


def code_gen(inputs, task_id):
    video = inputs["embed"]
    uri = video.kw["uri"].text
    title = inputs["title"].text
    html = f'<!doctype html><title>{title}</title><h1>{title}</h1><video src="{uri}" controls autoplay loop></video>'
    return {"id": "page-1", "type": "code", "content": html, "mime": "text/html",
            "hash": "sha256:" + hashlib.sha256(html.encode()).hexdigest()[:16]}


# ---------------------------------------------------------------------- planner (demo)

def video_page_recipe(goal: str):
    return [
        TaskSpec("t1", "image-gen", {"prompt": Str("Tokyo skyline at night, photorealistic"), "width": Quantity(1920, "px"), "height": Quantity(1080, "px")}),
        TaskSpec("t2", "video-gen", {"keyframe": TaskRef("t1"), "duration": Quantity(10, "s"), "motion": aicl.Symbol("slow-pan")}),
        TaskSpec("t3", "code-gen", {"embed": TaskRef("t2"), "title": Str("Tokyo at night")}),
    ]


PLANNER = RecipePlanner([
    (["動画", "video"], video_page_recipe),
    (["画像", "image"], lambda goal: [TaskSpec("t1", "image-gen", {"prompt": Str(goal)})]),
])


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    bus = Bus()
    hub = Hub(PLANNER)
    img, vid, code = SkillAgent("img", "image-gen", image_gen), SkillAgent("vid", "video-gen", video_gen), SkillAgent("code", "code-gen", code_gen)
    user = aicl.coop.Agent("user")
    bus.add(hub, img, vid, code, user)

    for a in (img, vid, code):            # registration: each specialist broadcasts its skill
        for f in a.announce("hub"):
            bus.send(f)

    goal = user.msg("do", "hub", form("coop:goal", nl("ja", "東京の夜景の10秒動画を作って、それを埋め込んだWebページを作って")))
    bus.send(goal)

    print("--- transcript (readable) ---")
    print(bus.text())
    issues = bus.check()
    errors = [i for i in issues if i.level == "error"]
    print("\n--- protocol check ---")
    for i in issues:
        print(" ", i)
    dense = "\n".join(aicl.to_dense(m.to_form()) for m in bus.transcript)
    print(f"{len(bus.transcript)} messages, {len(errors)} errors, "
          f"{tokens.count(bus.text())} tokens readable / {tokens.count(dense)} dense ({tokens.METHOD}), "
          f"nl ratio {aicl.nl_ratio(bus.transcript):.1%}")
    assert not errors
    final = bus.transcript[-1]
    assert final.act == "done" and final.receiver == "user"
    print("\n--- artifacts delivered to user ---")
    for a in final.body[0].items:
        print(" ", aicl.to_text(a)[:110])


if __name__ == "__main__":
    main()
