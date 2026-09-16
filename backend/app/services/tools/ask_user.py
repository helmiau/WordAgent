"""User clarification handled by LangChain HumanInTheLoopMiddleware."""

from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator


class AskUserInput(BaseModel):
    question: str = Field(min_length=1, max_length=1000, description="The clarification question.")
    options: list[str] = Field(default_factory=list, max_length=4, description="Provide 2–4 concise, distinct answer options, or omit for free text. Never exceed four.")

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


def build_ask_user(description: str):
    """Build the ask_user tool with the supplied description."""

    @tool(description=description, args_schema=AskUserInput)
    def ask_user(question: str, options: list[str] | None = None) -> str:
        # A respond decision supplies the ToolMessage without executing this function.
        raise RuntimeError("ask_user 必须通过人在回路中间件等待用户回答")

    return ask_user
