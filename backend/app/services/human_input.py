"""Serialize persisted HITL interrupts and validate user answers before resuming."""

import json

from langgraph.types import Command

from app.services.tools.ask_user import AskUserInput


def pending_questions(interrupts) -> dict | None:
    questions = []
    for item in interrupts:
        value = item.value
        if not isinstance(value, dict):
            raise ValueError("无法识别待处理的用户确认")
        actions = value.get("action_requests", [])
        for index, action in enumerate(actions):
            if action.get("name") != "ask_user":
                raise ValueError("存在不支持的待确认工具")
            raw_args = dict(action.get("args", {}))
            # Older checkpoints may contain up to six options. Keep these questions
            # answerable after upgrading without exposing an oversized option list.
            legacy = "questions" not in raw_args
            if legacy:
                options = raw_args.get("options")
                if isinstance(options, list):
                    options = list(
                        dict.fromkeys(
                            option.strip() for option in options if isinstance(option, str) and option.strip()
                        )
                    )[:4]
                    raw_args["options"] = options if len(options) >= 2 else []
            args = AskUserInput.model_validate(raw_args)
            for question_index, question in enumerate(args.questions):
                question_id = f"{item.id}:{index}"
                if not legacy:
                    question_id += f":{question_index}"
                questions.append({"id": question_id, **question.model_dump()})
    return {"type": "ask_user", "questions": questions} if questions else None


async def load_pending_questions(checkpointer, config: dict) -> tuple[list, dict | None]:
    saved = await checkpointer.aget_tuple(config)
    interrupts = []
    seen = set()
    for _, channel, value in (saved.pending_writes or []) if saved else []:
        if channel == "__interrupt__":
            for item in value:
                if item.id not in seen:
                    seen.add(item.id)
                    interrupts.append(item)
    return interrupts, pending_questions(interrupts)


def answer_command(interrupts, response: dict) -> Command:
    pending = pending_questions(interrupts)
    if not pending:
        raise ValueError("这个问题已回答或已失效，请刷新会话")
    answers = response.get("answers") if isinstance(response, dict) else None
    if not isinstance(answers, list) or len(answers) != len(pending["questions"]):
        raise ValueError("请回答所有问题后再继续")
    by_id = {}
    for answer in answers:
        if not isinstance(answer, dict):
            raise ValueError("回答格式不正确")
        question_id, text = answer.get("id"), answer.get("answer")
        if not isinstance(question_id, str) or question_id in by_id:
            raise ValueError("问题已失效或重复提交，请刷新会话")
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise ValueError("回答须为 1–4000 字的非空文本")
        by_id[question_id] = text.strip()
    if set(by_id) != {question["id"] for question in pending["questions"]}:
        raise ValueError("问题已失效，请刷新会话后重新回答")
    questions_by_id = {question["id"]: question for question in pending["questions"]}
    resume = {}
    for item in interrupts:
        decisions = []
        for index, action in enumerate(item.value["action_requests"]):
            action_id = f"{item.id}:{index}"
            if "questions" in action["args"]:
                # HITL expects one decision per tool call, not one per question.
                answers = []
                for question_index in range(len(action["args"]["questions"])):
                    question_id = f"{action_id}:{question_index}"
                    answers.append(
                        {
                            "question": questions_by_id[question_id]["question"],
                            "answer": by_id[question_id],
                        }
                    )
                message = json.dumps({"answers": answers}, ensure_ascii=False)
            else:
                message = by_id[action_id]
            decisions.append({"type": "respond", "message": message})
        resume[item.id] = {"decisions": decisions}
    return Command(resume=resume)
