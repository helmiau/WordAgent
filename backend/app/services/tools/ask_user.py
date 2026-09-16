"""User clarification handled by LangChain HumanInTheLoopMiddleware."""

from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator, model_validator


class AskUserQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=1000, description="The clarification question.")
    options: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="Provide 2–4 concise, distinct answer options, or omit for free text. Never exceed four.",
    )

    @field_validator("question")
    @classmethod
    def clean_question(cls, value):
        if not value.strip():
            raise ValueError("问题不能为空")
        return value.strip()

    @field_validator("options")
    @classmethod
    def clean_options(cls, values):
        if any(not value.strip() or len(value) > 300 for value in values):
            raise ValueError("选项须为 1–300 字的非空文本")
        options = list(dict.fromkeys(value.strip() for value in values))
        if len(options) == 1:
            raise ValueError("请提供 2–4 个不同的选项，或留空让用户自行填写")
        return options


class AskUserInput(BaseModel):
    questions: list[AskUserQuestion] = Field(
        min_length=1,
        max_length=4,
        description="Ask 1–4 necessary questions together; each has 2–4 options or no options for free text.",
    )

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_question(cls, value):
        if isinstance(value, dict):
            if "questions" in value and ("question" in value or "options" in value):
                raise ValueError("请使用 questions 数组，不要混用单题格式")
            if "questions" not in value and "question" in value:
                return {"questions": [{"question": value["question"], "options": value.get("options", [])}]}
        return value


def build_ask_user(description: str):
    """Build the ask_user tool with the supplied description."""

    @tool(description=description, args_schema=AskUserInput)
    def ask_user(questions: list[dict]) -> str:
        # A respond decision supplies the ToolMessage without executing this function.
        raise RuntimeError("ask_user 必须通过人在回路中间件等待用户回答")

    return ask_user
