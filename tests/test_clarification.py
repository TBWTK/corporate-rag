from rag_app.generation.response import parse_model_response


def test_parse_structured_clarification() -> None:
    raw = """```json
    {
      "response_type": "clarification",
      "question": "Для какого подразделения проверить правило?",
      "options": ["Отдел продаж", "Разработка", "Региональный офис"]
    }
    ```"""

    result = parse_model_response(raw)

    assert result.response_type == "clarification"
    assert result.text == "Для какого подразделения проверить правило?"
    assert result.options == ["Отдел продаж", "Разработка", "Региональный офис"]


def test_parse_structured_answer_and_plain_text_fallback() -> None:
    answer = parse_model_response(
        '{"response_type":"answer","answer":"Лимит — 10 000 рублей [1]."}'
    )
    fallback = parse_model_response("Обычный ответ провайдера [1].")

    assert answer.response_type == "answer"
    assert answer.text == "Лимит — 10 000 рублей [1]."
    assert answer.options == []
    assert fallback.response_type == "answer"
    assert fallback.text == "Обычный ответ провайдера [1]."


def test_invalid_clarification_falls_back_without_fake_options() -> None:
    raw = '{"response_type":"clarification","question":"Уточните отдел","options":["Один"]}'

    result = parse_model_response(raw)

    assert result.response_type == "answer"
    assert result.options == []


def test_clarification_compacts_excess_options_and_preserves_catch_all() -> None:
    raw = """{
      "response_type": "clarification",
      "question": "Какое ваше подразделение?",
      "options": [
        "Продажи", "Инженерный отдел", "Продукт", "Финансы",
        "Поддержка", "Дизайн", "Другое"
      ]
    }"""

    result = parse_model_response(raw)

    assert result.response_type == "clarification"
    assert result.options == [
        "Продажи",
        "Инженерный отдел",
        "Продукт",
        "Финансы",
        "Другое",
    ]
