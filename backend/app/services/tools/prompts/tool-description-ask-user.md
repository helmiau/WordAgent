Ask the user for clarification and pause when missing information would materially affect the result.

## Signature
`ask_user(questions: list[{question: str, options?: list[str]}]) -> str`

## Parameters
- `questions`: 1–4 necessary, independent questions to show together in one panel. Use one question when that is all you need; batch known missing requirements instead of asking one per round.
- Each `question`: One specific question, up to 1,000 characters.
- Each `options`: 2–4 concise, distinct answers, each up to 300 characters, or omit for free text. The user can always enter their own answer.

## Notes
- Wait for all answers before continuing dependent work. The tool result contains the question/answer pairs. Never invent an answer.
- Do not ask about information already supplied or ordinary implementation details; do not invent extra questions just to fill the panel. Defer questions whose meaning depends on an earlier answer.
- When clarification is needed, call only `ask_user` in that turn. The human-in-the-loop middleware supplies the answers and resumes execution.
