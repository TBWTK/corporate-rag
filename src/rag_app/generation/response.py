from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

ResponseType = Literal["answer", "clarification"]


@dataclass(frozen=True, slots=True)
class ModelResponse:
    response_type: ResponseType
    text: str
    options: list[str]


def parse_model_response(raw: str) -> ModelResponse:
    clean = raw.strip()
    json_text = _strip_code_fence(clean)
    try:
        payload = json.loads(json_text, strict=False)
    except (json.JSONDecodeError, TypeError):
        return ModelResponse(response_type="answer", text=clean, options=[])
    if isinstance(payload, str):
        try:
            payload = json.loads(_strip_code_fence(payload.strip()), strict=False)
        except (json.JSONDecodeError, TypeError):
            return ModelResponse(response_type="answer", text=clean, options=[])
    if not isinstance(payload, dict):
        return ModelResponse(response_type="answer", text=clean, options=[])

    if payload.get("response_type") == "answer":
        answer = payload.get("answer")
        if isinstance(answer, str) and answer.strip():
            return ModelResponse(response_type="answer", text=answer.strip(), options=[])

    if payload.get("response_type") == "clarification":
        question = payload.get("question")
        raw_options = payload.get("options")
        if isinstance(question, str) and question.strip() and isinstance(raw_options, list):
            options = _limit_options(_clean_options(raw_options))
            if 2 <= len(options) <= 5:
                return ModelResponse(
                    response_type="clarification",
                    text=question.strip(),
                    options=options,
                )

    return ModelResponse(response_type="answer", text=clean, options=[])


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```") or not text.endswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) < 3:
        return text
    return "\n".join(lines[1:-1]).strip()


def _clean_options(values: list[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        option = value.strip()
        if option and option not in result:
            result.append(option)
    return result


def _limit_options(options: list[str]) -> list[str]:
    if len(options) <= 5:
        return options
    catch_all = next(
        (
            option
            for option in reversed(options)
            if option.casefold().startswith(("друг", "иное", "иной", "не из"))
        ),
        None,
    )
    if catch_all is not None and catch_all not in options[:4]:
        return [*options[:4], catch_all]
    return options[:5]
