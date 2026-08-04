from __future__ import annotations

import json
from pathlib import Path

from rag_app.ingestion.extractors import SUPPORTED_EXTENSIONS, extract_document

CORPUS = Path("examples/acme-corp")


def test_demo_corpus_has_twenty_extractable_documents_and_all_formats() -> None:
    documents = sorted(path for path in CORPUS.iterdir() if path.is_file())

    assert len(documents) == 20
    assert {path.suffix.lower() for path in documents} == set(SUPPORTED_EXTENSIONS) - {".htm"}
    for path in documents:
        extracted = extract_document(path)
        assert sum(len(unit.text) for unit in extracted.units) >= 120, path.name


def test_demo_corpus_contains_linked_additional_agreements() -> None:
    agreements = sorted(CORPUS.glob("additional_agreement_*"))

    assert len(agreements) >= 6
    for path in agreements:
        text = "\n".join(unit.text for unit in extract_document(path).units).casefold()
        assert "дополнительное соглашение" in text, path.name
        assert "область действия" in text, path.name
        assert "приоритет" in text, path.name
        assert "дата вступления" in text, path.name


def test_demo_cases_cover_answers_clarifications_and_two_turn_flows() -> None:
    cases = json.loads(Path("examples/demo_cases.json").read_text(encoding="utf-8"))

    assert len(cases) >= 12
    kinds = {case["kind"] for case in cases}
    assert kinds == {"answer", "clarification", "two_turn"}
    assert all(case.get("question") and case.get("expected") for case in cases)
