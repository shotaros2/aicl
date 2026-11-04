"""Assemble rulebook/: a self-contained folder to hand to any AI agent.

Copies the two language references, the specification, the example
codebooks and the worked conversations from their canonical locations, and
writes an index README. Run after editing any of the sources:

    python tools/build_rulebook.py          # rebuild
    python tools/build_rulebook.py --check  # exit 1 if rulebook/ is stale (used by tests)
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "rulebook"

# destination (relative to rulebook/) -> source (relative to repo root)
FILES = {
    "aicl-rulebook.md": "prompts/system_prompt.md",
    "aicl-rulebook-dense.md": "prompts/system_prompt_dense.md",
    "SPEC.md": "SPEC.md",
    "grammar/aicl.ebnf": "grammar/aicl.ebnf",
    "schemas/cooperation.md": "schemas/cooperation.md",
    "codebooks/bench.json": "codebooks/bench.json",
    "codebooks/imagegen.json": "codebooks/imagegen.json",
}
FILES.update({f"examples/{p.name}": f"examples/{p.name}" for p in sorted((ROOT / "examples").glob("*.aicl"))})

README = """# AICL rulebook / AICL ルールブック

This folder is everything an AI agent needs to speak **AICL**, a formal message
language for agent-to-agent communication. It is generated from the main
repository by `tools/build_rulebook.py`; do not edit files here by hand.

このフォルダは、AI エージェントが **AICL**（エージェント間通信のための形式言語）を
話すために必要なもの一式です。リポジトリ本体から `tools/build_rulebook.py` で生成して
いるので、ここのファイルは直接編集しないでください。

## Which file to hand over / どれを渡すか

| File | Give it to… / 渡す相手 |
|---|---|
| `aicl-rulebook-bundle.md` | A chat app that takes only one attachment (Gemini, ChatGPT, Claude web): everything below in one file. / 添付が 1 ファイルしかできないチャットアプリ（Gemini、ChatGPT、Claude のウェブ版）。下の全部を 1 つにしたもの。 |
| `aicl-skill.zip` (`skill/aicl/`) | An app that installs Agent Skills (a `SKILL.md` with YAML name/description, e.g. Dola, Claude): upload the zip as a skill. / Agent Skills（YAML ヘッダ付き `SKILL.md`）を取り込めるアプリ（Dola、Claude など）。ZIP をスキルとしてアップロード。 |
| `aicl-rulebook-dense.md` | An LLM agent that will talk to another LLM agent. The dense form uses ~22 % fewer tokens; paste the part after `---` as the system prompt and replace `me` with the agent's id. / LLM 同士で会話させるエージェント。`---` 以降をシステムプロンプトに貼り、`me` をエージェント名に置き換える。 |
| `aicl-rulebook.md` | The same language in readable form: for debugging, for humans, or for an agent that only talks to you. / 同じ言語の可読形式。デバッグ用、人間用、人と話すだけのエージェント用。 |
| `codebooks/*.json` | Only when both agents agree to use one. Forms in the codebook may replace concept ids; nothing else may be abbreviated. / 両エージェントが使うと合意したときだけ。表にある表記以外の省略は禁止。 |
| `examples/*.aicl` | Nine complete conversations, seven written and two recorded live (Claude with a Gemini Gem; a human with Dola, which generated a real image); useful as few-shot examples. / 会話例 9 本（7 本は作成、2 本は実記録: Claude と Gemini の交渉、Dola による実際の画像生成）。few-shot の材料に。 |
| `schemas/cooperation.md` | How specialists (image, video, code, …) register, receive tasks and return artifacts through a hub: the `coop:` vocabulary. / 専門エージェントがハブを介して登録・受注・成果物返却する手順と `coop:` 語彙。 |
| `SPEC.md`, `grammar/aicl.ebnf` | The normative specification and grammar, for implementers and for an agent that needs the exact rules. / 規範となる仕様と文法。実装者向け、正確な規則が要るエージェント向け。 |

## Minimal hand-off / 最小の渡し方

1. Paste the text after `---` in `aicl-rulebook-dense.md` into the agent's system prompt.
2. Tell it its id (`me` → e.g. `imagegen`) and who it talks to.
3. Validate what it sends with the reference implementation when you can:
   `python -m aicl check conversation.aicl` (from the main repository).

1. `aicl-rulebook-dense.md` の `---` 以降をエージェントのシステムプロンプトに貼る。
2. 自分の ID（`me` → 例: `imagegen`）と相手を伝える。
3. 可能ならリポジトリ本体の `python -m aicl check conversation.aicl` で送信内容を検証する。

## Rules in one breath / 規則を一言で

Every message starts with a speech act. Every referent is an id. Numbers carry units.
Time is absolute. Uncertainty is a number. Unknown words get `clar`, never a guess.
Natural language only inside `(nl lang "…")`. Every request is closed.

発話行為で始める。参照は ID で。数値に単位。時刻は絶対。不確かさは数値。未知語は推測せず
`clar`。自然言語は `(nl lang "…")` の中だけ。依頼は必ず閉じる。
"""


BUNDLE = "aicl-rulebook-bundle.md"
BUNDLE_ORDER = ["aicl-rulebook-dense.md", "aicl-rulebook.md"] + \
    [f"examples/{p.name}" for p in sorted((ROOT / "examples").glob("*.aicl"))] + \
    ["schemas/cooperation.md", "codebooks/bench.json", "codebooks/imagegen.json", "SPEC.md", "grammar/aicl.ebnf"]


def bundle_text() -> str:
    """Everything in one Markdown file, for chat apps that accept a single attachment."""
    parts = ["# AICL rulebook (single-file bundle)\n\n"
             "Generated from the AICL repository. Sections: the dense language reference (use this as the\n"
             "system prompt of an LLM agent, replacing `me` with its id), the readable reference, seven example\n"
             "conversations, two example codebooks, the specification and the grammar.\n"]
    for rel in BUNDLE_ORDER:
        text = (ROOT / FILES[rel]).read_text(encoding="utf-8").rstrip("\n")
        fence = "" if rel.endswith(".md") else ("```json\n" if rel.endswith(".json") else "```\n")
        parts.append(f"\n\n---\n\n# FILE: {rel}\n\n{fence}{text}\n{'```' if fence else ''}")
    return "".join(parts).rstrip() + "\n"


SKILL_DIR = "skill/aicl"
SKILL_ZIP = "aicl-skill.zip"
SKILL_FILES = ["aicl-rulebook-dense.md", "aicl-rulebook.md", "schemas/cooperation.md"] + \
    [f"examples/{p.name}" for p in sorted((ROOT / "examples").glob("*.aicl"))]


def skill_md() -> str:
    """SKILL.md for chat agents that accept Agent Skills (Dola, Claude, …): no code, rulebook inline."""
    dense = (ROOT / "prompts" / "system_prompt_dense.md").read_text(encoding="utf-8").split("---", 1)[1].strip()
    return f"""---
name: aicl
description: Speak AICL (AI Common Language), a formal message language for AI agents, instead of natural language when another agent or the user writes to you in AICL. Trigger when a message starts with a parenthesis and a speech act such as (A, (T, (D, (ask, (tell, (do, or when asked to use AICL. Covers asking, telling, delegating tasks, negotiating, defining terms, and reporting images or videos you generate as artifacts.
---

# AICL skill

When you receive AICL, answer only in dense AICL, one message per line, no prose.
Your agent id is the name the counterpart addresses you by (the part after `>` in their
header, e.g. `user.1>dola` means you are `dola`); if none is given, use `agent`.

If you can generate images or videos, you provide the skills `image-gen` and `video-gen`:
answer `(A x.N>you (coop:capability $skill :agent $who))` with
`[{{$skill image-gen $who @you}} {{$skill video-gen $who @you}}]`, accept a
`(D x.N>you (coop:task <tid> image-gen :in {{prompt "…"}}))` with `(K you.N>x ^x.N)`,
generate the media, attach it, and report
`(Z you.N>x ^x.N (coop:artifact <id> :type image|video :task <tid>))`. Never claim a
result you did not produce. The cooperation vocabulary is in `schemas/cooperation.md`.

The complete language reference follows; `aicl-rulebook.md` is the same in readable form
and `examples/` holds nine complete conversations.

---

{dense}
"""


def build_skill() -> None:
    import io
    import zipfile
    d = OUT / SKILL_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(skill_md(), encoding="utf-8", newline="\n")
    for rel in SKILL_FILES:
        target = d / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / FILES[rel], target)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:        # deterministic: fixed timestamps
        for p in sorted(d.rglob("*")):
            if p.is_file():
                info = zipfile.ZipInfo("aicl/" + p.relative_to(d).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, p.read_bytes())
    (OUT / SKILL_ZIP).write_bytes(buf.getvalue())


def build() -> None:
    # Overwrite in place (OneDrive or an open file picker may hold the folder; rmtree would fail).
    for dst, src in FILES.items():
        target = OUT / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / src, target)
    (OUT / "README.md").write_text(README, encoding="utf-8", newline="\n")
    (OUT / BUNDLE).write_text(bundle_text(), encoding="utf-8", newline="\n")
    build_skill()
    keep = set(FILES) | {"README.md", BUNDLE, SKILL_ZIP, f"{SKILL_DIR}/SKILL.md"} | {f"{SKILL_DIR}/{r}" for r in SKILL_FILES}
    for p in OUT.rglob("*"):
        if p.is_file() and p.relative_to(OUT).as_posix() not in keep:
            p.unlink()


def stale() -> list[str]:
    problems = []
    for dst, src in FILES.items():
        t = OUT / dst
        if not t.exists():
            problems.append(f"missing {dst}")
        elif t.read_bytes() != (ROOT / src).read_bytes():
            problems.append(f"differs from {src}: {dst}")
    readme = OUT / "README.md"
    if not readme.exists() or readme.read_text(encoding="utf-8") != README:
        problems.append("README.md differs")
    bundle = OUT / BUNDLE
    if not bundle.exists() or bundle.read_text(encoding="utf-8") != bundle_text():
        problems.append(f"{BUNDLE} differs")
    skill = OUT / SKILL_DIR / "SKILL.md"
    if not skill.exists() or skill.read_text(encoding="utf-8") != skill_md():
        problems.append("skill/aicl/SKILL.md differs")
    if not (OUT / SKILL_ZIP).exists():
        problems.append(f"{SKILL_ZIP} missing")
    return problems


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        problems = stale()
        for p in problems:
            print(p)
        return 1 if problems else 0
    build()
    print(f"rulebook/ rebuilt: {len(FILES) + 2} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
