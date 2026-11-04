import unittest
from pathlib import Path

import aicl
from aicl.coop import RecipePlanner, SkillAgent, TaskSpec
from aicl.gateway import Gateway, artifact_path
from aicl.model import Str


def fake_image(inputs, tid):
    return {"id": f"img-{tid}", "type": "image", "uri": "file:///C:/tmp/out/t1.png", "mime": "image/png"}


def make():
    planner = RecipePlanner([(["image", "画像"], lambda g: [TaskSpec("t1", "image-gen", {"prompt": Str(g)})])])
    return Gateway("claude", [SkillAgent("img", "image-gen", fake_image)], planner)


class GatewayTests(unittest.TestCase):
    def test_direct_task_to_specialist(self):
        gw = make()
        ex = gw.send('(D claude.1>img (coop:task t1 image-gen :in {prompt "Tokyo at night"}))')
        self.assertEqual(ex.errors, [])
        self.assertEqual([m.act for m in ex.replies], ["ok", "done"])
        self.assertEqual(len(ex.artifacts), 1)
        self.assertEqual(artifact_path(ex.artifacts[0]), Path("C:/tmp/out/t1.png"))
        self.assertEqual([i for i in gw.bus.check() if i.level == "error"], [])

    def test_goal_through_hub(self):
        gw = make()
        ex = gw.send('(do #claude.1 @claude>@hub (coop:goal (nl ja "東京の夜景の画像")))')
        self.assertEqual([m.act for m in ex.replies], ["ok", "tell", "done"])
        self.assertEqual(len(ex.artifacts), 1)
        self.assertEqual(gw.capabilities(), {"image-gen": "img"})

    def test_rejects_wrong_sender_and_bad_syntax(self):
        gw = make()
        ex = gw.send("(D hub.1>img (coop:task t1 image-gen))")
        self.assertEqual(ex.replies, [])
        self.assertIn("claims to be from @hub", ex.errors[0])
        ex = gw.send("this is not aicl")
        self.assertTrue(ex.errors and "must be a form" in ex.errors[0])
        ex = gw.send("(K claude.2>img)")                    # ok without ^reply: protocol error, not delivered
        self.assertTrue(ex.errors and "reply-required" in ex.errors[0])

    def test_numbering_follows_requester(self):
        gw = make()
        gw.send('(D claude.5>img (coop:task t1 image-gen :in {prompt "x"}))')
        self.assertEqual(gw.requester.seq, 5)
        self.assertIn("(do #claude.5 @claude>@img", gw.transcript())
        self.assertEqual(len(gw.artifacts()), 1)


if __name__ == "__main__":
    unittest.main()
