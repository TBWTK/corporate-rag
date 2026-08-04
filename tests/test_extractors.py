from pathlib import Path

import pytest

from rag_app.ingestion.extractors import UnsupportedDocumentError, extract_document


@pytest.mark.parametrize(
    ("filename", "payload", "expected"),
    [
        ("policy.txt", "Отпуск согласует руководитель".encode(), "Отпуск согласует"),
        ("guide.md", "# Инструкция\n\nИспользуйте VPN".encode(), "Используйте VPN"),
        ("limits.csv", "тип,лимит\nтакси,2500\n".encode(), "такси | 2500"),
    ],
)
def test_extract_document_for_text_formats(
    tmp_path: Path, filename: str, payload: bytes, expected: str
) -> None:
    path = tmp_path / filename
    path.write_bytes(payload)

    document = extract_document(path)

    assert document.title == filename
    assert expected in "\n".join(unit.text for unit in document.units)
    assert all(unit.location for unit in document.units)


def test_extract_document_rejects_unknown_format(tmp_path: Path) -> None:
    path = tmp_path / "archive.zip"
    path.write_bytes(b"not a document")

    with pytest.raises(UnsupportedDocumentError, match=".zip"):
        extract_document(path)
