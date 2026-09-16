## ask_user Usage Policy

- Use only when missing information or ambiguity would materially change the result.
- Send a `questions` array containing 1–4 necessary questions in one call. Gather independent missing requirements together to avoid repeated clarification rounds; ask just one when sufficient. Defer dependent follow-ups until their prerequisite is answered.
- Each question may have 2–4 concise, distinct options or no options for free text. Never exceed four options; the user can always enter their own answer.
- Wait for all answers before dependent work. Do not invent answers, repeat known questions, or request confirmation for routine implementation details.
- Call only `ask_user` in a clarification turn, without other tools that could perform premature actions.
