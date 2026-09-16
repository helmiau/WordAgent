"""Resolve edit styles from checkpoint state and stop unproductive document writes.

No shared document/style cache: every tool invocation derives its context from its
own thread's messages. Public tool schemas and paragraph styles remain unchanged.
"""

import json
from contextvars import ContextVar

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

edit_style_context: ContextVar[dict | None] = ContextVar("edit_style_context", default=None)
MUTATIONS = {"edit_document", "delete_document", "generate_document", "insert_break"}


def _payload(message):
    try:
        value = json.loads(message.content) if isinstance(message.content, str) else message.content
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _doc_id(args, state):
    value = str(args.get("docId") or "0")
    if value == "0":
        meta = state.get("request_context", {}).get("document_meta") or []
        if isinstance(meta, dict):
            meta = [meta]
        if meta:
            value = str(meta[0].get("documentId") or "0")
    return value


def _targets(name, args):
    values = (
        args.get("paraIDs", [])
        if name == "delete_document"
        else [args.get("insertParaID" if name == "generate_document" else "paraID")]
    )
    return {str(value) for value in values if value is not None}


def _paragraph_ids(value):
    ids = set()
    if isinstance(value, dict):
        if value.get("paraID") is not None:
            ids.add(str(value["paraID"]))
        for item in value.values():
            ids.update(_paragraph_ids(item))
    elif isinstance(value, list):
        for item in value:
            ids.update(_paragraph_ids(item))
    return ids


def prepare_document_call(call, state):
    """Return (latest character-style dictionary, optional refusal payload)."""
    name, args = call["name"], call.get("args", {})
    if name not in MUTATIONS:
        return {}, None
    doc_id = _doc_id(args, state)
    messages = state.get("messages", [])
    turn_start = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=0)
    calls, events, styles = {}, [], {}
    for index, message in enumerate(messages):
        if isinstance(message, AIMessage):
            calls.update({item["id"]: (item, index) for item in message.tool_calls})
        elif isinstance(message, ToolMessage):
            matched = calls.get(message.tool_call_id)
            if not matched:
                continue
            previous, call_index = matched
            # The active document may have changed between user turns. Never
            # reinterpret an old docId=0 against today's active document.
            if call_index < turn_start and str(previous.get("args", {}).get("docId") or "0") == "0":
                continue
            if _doc_id(previous.get("args", {}), state) != doc_id:
                continue
            data = _payload(message)
            tool_name = previous["name"]
            if tool_name == "read_document" and not data.get("error") and isinstance(data.get("styles"), dict):
                styles = data["styles"]
            elif tool_name == "generate_document" and data.get("success") is True:
                document = previous.get("args", {}).get("document", {})
                if isinstance(document, dict) and isinstance(document.get("styles"), dict):
                    styles = document["styles"]
            if index >= turn_start:
                events.append((previous, data, message.status))

    target = _targets(name, args)

    def refuse(code, text):
        return styles, {
            "success": False,
            "errorCode": code,
            "error": text,
            "docId": args.get("docId", 0),
            "retryable": False,
            "requiresRead": code == "document_state_unverified",
        }

    # A failure/timeout can leave real side effects. A fresh read must establish
    # the next target, rather than trusting a rollback claim or stale paraID.
    for index in range(len(events) - 1, -1, -1):
        previous, data, status = events[index]
        if previous["name"] not in MUTATIONS or data.get("errorCode") in {"document_state_unverified", "no_progress"}:
            continue
        if data.get("success") is not True or status == "error":
            reads = [
                d
                for c, d, s in events[index + 1 :]
                if c["name"] == "read_document"
                and s != "error"
                and not d.get("error")
                and isinstance(d.get("paragraphs"), list)
            ]
            if not reads or not target or not target.issubset(_paragraph_ids(reads[-1])):
                return refuse(
                    "document_state_unverified",
                    "上次写操作失败或结果未确认。请先 read_document 读取目标区域，使用返回的有效 paraID；不要直接重试或删除重建。",
                )
        break

    failures = sum(
        1
        for c, d, s in events
        if c["name"] in MUTATIONS
        and target.intersection(_targets(c["name"], c.get("args", {})))
        and (d.get("success") is not True or s == "error")
        and d.get("errorCode") not in {"document_state_unverified", "no_progress"}
    )
    if failures >= 2:
        return refuse(
            "no_progress", "本轮该段落已两次修正失败，停止进一步修改或删除重建。保留已有结果并向用户说明限制。"
        )
    if any(
        d.get("errorCode") == "no_progress" and target.intersection(_targets(c["name"], c.get("args", {})))
        for c, d, _ in events
    ):
        return refuse("no_progress", "本轮已停止该段落的无进展修正，不能通过删除重建绕过；请保留已有结果并说明限制。")
    if name == "delete_document":
        edits = [
            c
            for c, d, _ in events
            if c["name"] == "edit_document"
            and target.intersection(_targets(c["name"], c.get("args", {})))
            and not d.get("errorCode")
        ]
        for para_id in target:
            texts = [
                "".join(str(r.get("text") or "") for r in c.get("args", {}).get("runs", []))
                for c in edits
                if para_id in _targets(c["name"], c.get("args", {}))
            ]
            if len(texts) >= 2 and texts[-1] == texts[-2]:
                return refuse(
                    "no_progress",
                    "该段落已执行编辑及一次相同文字的格式修正，禁止继续删除重建；请保留已有结果并说明限制。",
                )
    if name == "edit_document":
        text = "".join(str(run.get("text") or "") for run in args.get("runs", []))
        attempts = sum(
            1
            for c, d, s in events
            if c["name"] == name
            and _targets(name, c.get("args", {})) == target
            and "".join(str(run.get("text") or "") for run in c.get("args", {}).get("runs", [])) == text
            and d.get("errorCode") not in {"document_state_unverified", "no_progress"}
        )
        if attempts >= 2:
            return refuse(
                "no_progress", "同一段落相同文字已执行编辑及一次修正，停止继续尝试字符格式；请保留已有结果并说明限制。"
            )
    return styles, None
