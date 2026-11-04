import unittest

import aicl
from aicl.build import form, nl
from aicl.coop import (
    Agent, Bus, Hub, LLMPlanner, ProtocolError, RecipePlanner, SkillAgent, TaskRef, TaskSpec,
)
from aicl.model import KList, KMap, Quantity, Str, Symbol


def img_fn(inputs, tid):
    return {"id": "a-img", "type": "image", "uri": "file://img.png"}


def vid_fn(inputs, tid):
    kf = inputs["keyframe"]
    assert isinstance(kf, aicl.Form) and kf.head == "coop:artifact", "artifact must be passed in full"
    return {"id": "a-vid", "type": "video", "uri": "file://vid.mp4"}


def code_fn(inputs, tid):
    return {"id": "a-page", "type": "code", "content": "<html>"}


def boom(inputs, tid):
    raise RuntimeError("GPU on fire")


RECIPE = RecipePlanner([(["video"], lambda g: [
    TaskSpec("t1", "image-gen", {"prompt": Str(g)}),
    TaskSpec("t2", "video-gen", {"keyframe": TaskRef("t1"), "duration": Quantity(10, "s")}),
    TaskSpec("t3", "code-gen", {"embed": TaskRef("t2")}),
])])


def make_bus(planner=RECIPE, video=vid_fn):
    bus = Bus()
    hub = Hub(planner)
    user = Agent("user")
    specialists = [SkillAgent("img", "image-gen", img_fn), SkillAgent("vid", "video-gen", video),
                   SkillAgent("code", "code-gen", code_fn)]
    bus.add(hub, user, *specialists)
    for s in specialists:
        for f in s.announce("hub"):
            bus.send(f)
    return bus, hub, user


class CoopTests(unittest.TestCase):
    def test_registry_from_announcements(self):
        bus, hub, user = make_bus()
        self.assertEqual(hub.registry, {"image-gen": "img", "video-gen": "vid", "code-gen": "code"})

    def test_goal_runs_tasks_in_dependency_order_and_validates(self):
        bus, hub, user = make_bus()
        bus.send(user.msg("do", "hub", form("coop:goal", nl("en", "make a video and a page"))))
        acts = [(m.act, m.sender, m.receiver) for m in bus.transcript[3:]]
        self.assertEqual(acts[:3], [("do", "user", "hub"), ("ok", "hub", "user"), ("tell", "hub", "user")])
        self.assertEqual([m.receiver for m in bus.transcript if m.act == "do" and m.sender == "hub"], ["img", "vid", "code"])
        final = bus.transcript[-1]
        self.assertEqual((final.act, final.receiver, final.reply), ("done", "user", "user.1"))
        self.assertEqual([a.args[0].name for a in final.body[0].items], ["a-img", "a-vid", "a-page"])
        self.assertEqual([i for i in bus.check() if i.level == "error"], [])
        self.assertEqual([i.code for i in bus.check()], [])          # no open requests either
        self.assertLess(aicl.nl_ratio(bus.transcript), 0.05)

    def test_specialist_failure_propagates_with_reference(self):
        bus, hub, user = make_bus(video=boom)
        bus.send(user.msg("do", "hub", form("coop:goal", nl("en", "video please"))))
        final = bus.transcript[-1]
        self.assertEqual((final.act, final.receiver, final.reply), ("fail", "user", "user.1"))
        self.assertEqual(final.kw["code"], Symbol("internal"))
        self.assertEqual(final.kw["why"].head, "ref")
        self.assertFalse(any(m.receiver == "code" for m in bus.transcript))   # t3 never dispatched
        self.assertEqual([i for i in bus.check() if i.level == "error"], [])

    def test_unknown_skill_is_refused_not_guessed(self):
        planner = RecipePlanner([(["speech"], lambda g: [TaskSpec("t1", "speech-gen", {})])])
        bus, hub, user = make_bus(planner)
        bus.send(user.msg("do", "hub", form("coop:goal", nl("en", "speech synthesis"))))
        final = bus.transcript[-1]
        self.assertEqual(final.act, "no")
        self.assertEqual(aicl.to_text(final.kw["why"]), "(unk speech-gen)")

    def test_no_recipe_means_no(self):
        bus, hub, user = make_bus()
        bus.send(user.msg("do", "hub", form("coop:goal", nl("en", "something else entirely"))))
        self.assertEqual(bus.transcript[-1].act, "no")

    def test_capability_query_with_variables(self):
        bus, hub, user = make_bus()
        bus.send(user.msg("ask", "vid", form("coop:capability", aicl.Var("s"), kw={"agent": aicl.Var("who")})))
        answer = bus.transcript[-1]
        self.assertEqual(answer.act, "tell")
        self.assertEqual(aicl.to_text(answer.body[0]), "{$s video-gen $who @vid}")

    def test_wrong_skill_sent_to_specialist(self):
        bus, hub, user = make_bus()
        bus.send(user.msg("do", "img", form("coop:task", Symbol("x"), Symbol("video-gen"))))
        self.assertEqual(bus.transcript[-1].act, "no")

    def test_bus_rejects_invalid_messages(self):
        bus, hub, user = make_bus()
        with self.assertRaises(ProtocolError):
            bus.send(aicl.parse_one("(ok #user.9 @user>@hub)"))          # ok without ^reply
        with self.assertRaises(ProtocolError):
            bus.send(user.msg("tell", "nobody", form("x")))

    def test_llm_planner_parses_and_checks_plan(self):
        plan = ('(coop:plan [(coop:task t1 image-gen :in {prompt "sunset"}) '
                '(coop:task t2 video-gen :in {keyframe (coop:from t1) duration 10s})])')
        specs = LLMPlanner(lambda prompt: plan)("goal", {"image-gen": "img", "video-gen": "vid"})
        self.assertEqual([s.id for s in specs], ["t1", "t2"])
        self.assertEqual(specs[1].needs, ["t1"])
        self.assertIsInstance(specs[1].inputs["keyframe"], TaskRef)
        with self.assertRaises(ValueError):
            LLMPlanner(lambda p: plan)("goal", {"image-gen": "img"})     # video-gen not available
        with self.assertRaises(ValueError):
            LLMPlanner(lambda p: "(tell #x @a>@b (y))")("goal", {})

    def test_llm_agent_returns_validated_messages(self):
        from aicl.coop import LLMAgent
        replies = {
            "ok+done": "(K code.1>hub ^hub.1)\n(Z code.2>hub ^hub.1 (coop:artifact page-t3 :type code :task t3 :content \"<html>\"))",
            "prose": "Sure! Here is the page.",
            "wrong-sender": "(K hub.9>code ^hub.1)",
        }
        state = {"mode": "ok+done"}
        agent = LLMAgent("code", lambda system, history: replies[state["mode"]], "rulebook @me", "role", ["code-gen"])
        bus = Bus()
        hub = Agent("hub")
        bus.add(agent, hub)
        task = hub.msg("do", "code", form("coop:task", Symbol("t3"), Symbol("code-gen")))
        bus.send(task)
        self.assertEqual([m.act for m in bus.transcript], ["do", "ok", "done"])
        self.assertEqual(agent.seq, 2)                       # numbering follows the model's own ids
        self.assertIn("; next-id code.1", agent.history[0]["content"])
        # the model reuses code.1/code.2 for the next task: the agent renumbers and keeps its replies coherent
        bus.send(hub.msg("do", "code", form("coop:task", Symbol("t5"), Symbol("code-gen"))))
        ids = [m.id for m in bus.transcript if m.sender == "code"]
        self.assertEqual(ids, ["code.1", "code.2", "code.3", "code.4"])
        self.assertEqual([i for i in bus.check() if i.code == "dup-id"], [])
        for mode in ("prose", "wrong-sender"):
            state["mode"] = mode
            bus.send(hub.msg("do", "code", form("coop:task", Symbol("t4"), Symbol("code-gen"))))
            self.assertEqual(bus.transcript[-1].act, "fail")
            self.assertEqual(bus.transcript[-1].kw["code"], Symbol("parse"))
        self.assertEqual(agent.corrections, 4)                # two attempts per failed task, both rejected
        self.assertEqual([i for i in bus.check() if i.level == "error"], [])

    def test_llm_agent_self_correction_turn(self):
        from aicl.coop import LLMAgent
        answers = iter(["(K code.1>#hub ^hub.1)",                                   # malformed header, like a real run
                        "(K code.1>hub ^hub.1)\n(Z code.2>hub ^hub.1 (coop:artifact p :type code :task t1))"])
        seen = []
        def ask(system, history):
            seen.append(history[-1]["content"])
            return next(answers)
        agent = LLMAgent("code", ask, "rulebook", "role", ["code-gen"])
        bus = Bus(); hub = Agent("hub"); bus.add(agent, hub)
        bus.send(hub.msg("do", "code", form("coop:task", Symbol("t1"), Symbol("code-gen"))))
        self.assertEqual([m.act for m in bus.transcript], ["do", "ok", "done"])
        self.assertEqual(agent.corrections, 1)
        self.assertTrue(seen[1].startswith("; your reply was invalid AICL:"))
        self.assertIn("; resend.\n; next-id code.1\n; reply header: code.1>hub ^hub.1", seen[1])

    def test_task_form_resolves_artifacts(self):
        spec = TaskSpec("t2", "video-gen", {"keyframe": TaskRef("t1")})
        art = form("coop:artifact", Symbol("a1"), kw={"type": Symbol("image"), "task": Symbol("t1")})
        self.assertIn("(coop:artifact a1", aicl.to_text(spec.to_form({"t1": art})))
        self.assertIn("(coop:from t1)", aicl.to_text(spec.to_form()))


if __name__ == "__main__":
    unittest.main()
