from pathlib import Path

from rag_app.seed import collect_demo_documents


def test_collect_demo_documents_resolves_relative_path_from_workdir(
    tmp_path: Path, monkeypatch
) -> None:
    examples = tmp_path / "examples" / "acme-corp"
    examples.mkdir(parents=True)
    (examples / "travel.md").write_text("Командировки", encoding="utf-8")
    (examples / "security.txt").write_text("ИБ", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    paths = collect_demo_documents(Path("examples/acme-corp"))

    assert [path.name for path in paths] == ["security.txt", "travel.md"]
