from rag_app.generation.prompting import SourceContext, build_grounded_messages


def test_prompt_requires_grounding_and_numbered_citations() -> None:
    sources = [
        SourceContext(
            number=1,
            filename="travel-policy.md",
            location="раздел 3",
            text="Лимит гостиницы составляет 8 000 рублей.",
        )
    ]

    messages = build_grounded_messages("Какой лимит гостиницы?", sources)
    prompt = "\n".join(message["content"] for message in messages)

    assert "[1]" in prompt
    assert "travel-policy.md" in prompt
    assert "только" in prompt.lower()
    assert "недостаточно" in prompt.lower()
    assert "недовер" in prompt.lower()
    assert '"response_type": "clarification"' in prompt
    assert "не предполагай" in prompt.lower()
    assert "приложения или платформы" in prompt.lower()
    assert "больше пяти" in prompt.lower()
    assert "нумерованные шаги" in prompt.lower()
    assert "перед началом" in prompt.lower()
    assert "как проверить" in prompt.lower()
    assert "если не получилось" in prompt.lower()
    assert "не подменяй url" in prompt.lower()
    assert "точный url" in prompt.lower()
    assert "до последнего предоставленного шага" in prompt.lower()


def test_prompt_rejects_empty_question() -> None:
    try:
        build_grounded_messages("  ", [])
    except ValueError as error:
        assert "вопрос" in str(error).lower()
    else:
        raise AssertionError("Expected ValueError")
