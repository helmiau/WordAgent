Ask the user for clarification and pause execution when ambiguity or missing information would materially affect the result.

## Signature
`ask_user(question: str, options: list[str] | None = None) -> str`

## Parameters
- `question`: One specific question about the missing requirement, up to 1,000 characters.
- `options`: Provide 2–4 concise, mutually exclusive answers, each up to 300 characters. Never provide more than four options. Omit this parameter or pass an empty list when a free-text answer is more appropriate. The user can always enter their own answer.

## Notes
- Wait for the user's answer before continuing the original task. Never invent an answer or choose on the user's behalf.
- Do not ask again about information already provided or request confirmation for ordinary implementation details.
- When clarification is needed, call only `ask_user` in that turn. Call tools that depend on the answer only after receiving it.
- The human-in-the-loop middleware supplies the user's answer as the tool result and resumes execution.
