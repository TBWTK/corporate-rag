from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from rag_app.ingestion.extractors import SUPPORTED_EXTENSIONS, extract_document

CORPUS = Path("examples/acme-corp")

REQUESTED_EXPANSION = {
    "access_request_guide.txt",
    "additional_agreement_design_hybrid.pdf",
    "additional_agreement_finance_office.docx",
    "additional_agreement_support_shifts.docx",
    "corporate_email_setup.html",
    "corporate_resources_policy.md",
    "culture_code.pdf",
    "email_signature_policy.md",
    "employment_contract_template.docx",
    "first_day_checklist.csv",
    "first_weeks_materials.html",
    "flash_trainings.md",
    "internal_tools_guide.html",
    "it_architecture.md",
    "it_systems_catalog.csv",
    "occupational_health_safety.html",
    "office_rules.md",
    "personal_data_policy.html",
    "product_overview.md",
    "product_use_cases.html",
    "video_intro_engineering.txt",
    "video_intro_finance.txt",
    "video_intro_people_ops.txt",
    "video_intro_product.txt",
    "video_intro_sales.txt",
    "video_surveillance_policy.txt",
    "work_format_policy.html",
    "work_schedule_and_adaptation.xlsx",
    "working_conditions.md",
    "workplace_setup_guide.docx",
}


def test_demo_corpus_has_fifty_extractable_documents_and_all_formats() -> None:
    documents = sorted(path for path in CORPUS.iterdir() if path.is_file())

    assert len(documents) == 50
    assert {path.name for path in documents} >= REQUESTED_EXPANSION
    assert {path.suffix.lower() for path in documents} == set(SUPPORTED_EXTENSIONS) - {".htm"}
    for path in documents:
        extracted = extract_document(path)
        assert sum(len(unit.text) for unit in extracted.units) >= 120, path.name


def test_demo_corpus_contains_linked_additional_agreements() -> None:
    agreements = sorted(CORPUS.glob("additional_agreement_*"))

    assert len(agreements) >= 10
    for path in agreements:
        text = "\n".join(unit.text for unit in extract_document(path).units).casefold()
        assert "дополнительное соглашение" in text, path.name
        assert "область действия" in text, path.name
        assert "приоритет" in text, path.name
        assert "дата вступления" in text, path.name


def test_demo_cases_cover_answers_clarifications_and_two_turn_flows() -> None:
    cases = json.loads(Path("examples/demo_cases.json").read_text(encoding="utf-8"))

    assert len(cases) == 36
    assert Counter(case["kind"] for case in cases) == {
        "answer": 12,
        "clarification": 12,
        "two_turn": 12,
    }
    assert len({case["id"] for case in cases}) == len(cases)
    assert all(case.get("question") and case.get("expected") for case in cases)
    assert all(case.get("follow_up") for case in cases if case["kind"] == "two_turn")

    corpus_names = {path.name for path in CORPUS.iterdir() if path.is_file()}
    for case in cases:
        sources = case.get("source_files")
        assert sources, case["id"]
        assert set(sources) <= corpus_names, case["id"]
