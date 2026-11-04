# AICL rulebook / AICL ルールブック

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
| `aicl-rulebook-dense.md` | An LLM agent that will talk to another LLM agent. The dense form uses ~22 % fewer tokens; paste the part after `---` as the system prompt and replace `me` with the agent's id. / LLM 同士で会話させるエージェント。`---` 以降をシステムプロンプトに貼り、`me` をエージェント名に置き換える。 |
| `aicl-rulebook.md` | The same language in readable form: for debugging, for humans, or for an agent that only talks to you. / 同じ言語の可読形式。デバッグ用、人間用、人と話すだけのエージェント用。 |
| `codebooks/*.json` | Only when both agents agree to use one. Forms in the codebook may replace concept ids; nothing else may be abbreviated. / 両エージェントが使うと合意したときだけ。表にある表記以外の省略は禁止。 |
| `examples/*.aicl` | Six complete conversations covering every speech act; useful as few-shot examples. / 全発話行為を含む会話例 6 本。few-shot の材料に。 |
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
