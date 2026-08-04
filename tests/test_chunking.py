from rag_app.domain.chunking import chunk_text


def test_chunk_text_respects_limit_and_keeps_context_overlap() -> None:
    text = (
        "Раздел один описывает порядок согласования отпусков. "
        "Заявление подают руководителю заранее.\n\n"
        "Раздел два описывает компенсацию командировок. "
        "Чеки прикладывают к авансовому отчёту."
    )

    chunks = chunk_text(text, max_chars=90, overlap_chars=20, location="стр. 1")

    assert len(chunks) >= 2
    assert all(0 < len(chunk.text) <= 90 for chunk in chunks)
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.location == "стр. 1" for chunk in chunks)
    assert set(chunks[0].text.split()) & set(chunks[1].text.split())


def test_chunk_text_discards_blank_input() -> None:
    assert chunk_text(" \n\t ", max_chars=100, overlap_chars=10) == []
