@AGENTS.md

Continuing this project on another machine or in a new session: read `HANDOFF.md` first
(accounts, setup steps, what was learned, next candidates). Secrets live only in `.env`.

To speak AICL with another agent, load `prompts/system_prompt.md` first and validate
every outgoing message with `python -m aicl check`. To use AICL as a skill, copy this
folder to `.claude/skills/aicl/` (its `SKILL.md` is the entry point).
