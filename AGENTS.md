# Instructions for AI agents working in this repository

This repository defines **Koine**, a formal message language for agent-to-agent
communication. If you are an AI agent, there are two ways you may be here.

## 1. You were given this folder so you can *speak* Koine

1. Read `prompts/system_prompt_dense.md` in full (or `prompts/system_prompt.md` for
   the readable form, which is easier while debugging). The part after the `---` line
   is the language reference you must follow when composing messages to another agent.
   Both forms are the same language; `python -m koine fmt` converts dense to readable
   and `python -m koine dense` the other way.
2. Compose exactly one Koine message per turn when talking to another agent, and
   nothing else (no prose around it).
3. Before you send a message, validate it. From this folder:

   ```bash
   python -m koine check path/to/conversation.koine --known <term> ...
   ```

   or, after `pip install -e .`, `koine check …`. Fix every `error` line. A
   `warning … unresolved-term` means you used a word the other agent has not
   agreed to: introduce it with `(def …)` first, or expect a `(clar …)` reply.
4. If you receive a message you cannot interpret, do not guess. Reply with
   `(clar #id @you>@them ^their-id (unk term))` or `(amb term [candidates])`.
5. When a message you received is not valid Koine, reply
   `(fail … :code parse :why (nl en "<what was wrong>"))` rather than acting on it.
6. If you and the other agent share a codebook (`codebooks/*.json`), you may send
   packed messages: `python -m koine pack msg.kd --codebook codebooks/x.json --tokenizer <theirs>`
   and decode incoming ones with `python -m koine unpack`. Never shorten or translate a
   term by hand; only forms in the codebook are valid.

Worked conversations are in `examples/*.koine`; the normative spec is `SPEC.md`.

## 2. You are editing the repository

- Run the test suite after every change: `python -m unittest discover -s tests`.
  Also run `python examples/two_agents_demo.py` and `python bench/compare.py`.
- The language (`SPEC.md`, `grammar/koine.ebnf`) and the implementation (`koine/`)
  must change together, with an example and a test.
- Canonical form is frozen within a minor version; a change that alters the
  digest in `tests/test_roundtrip.py` needs a version bump and a CHANGELOG entry.
- No runtime dependencies in `koine/`. Keep it small enough to port in an afternoon.
- Keep `README.md` and `README.ja.md` saying the same thing.
- `rulebook/` is generated. After editing `prompts/`, `SPEC.md`, `grammar/`, `codebooks/`
  or `examples/`, run `python tools/build_rulebook.py`; the test suite fails if it is stale.
- Do not overstate token savings; the benchmark table in the README is measured.
