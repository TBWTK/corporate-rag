from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class VisualRenderingError(ValueError):
    """Страницы документа не удалось безопасно отрендерить."""


@dataclass(frozen=True, slots=True)
class RenderedPage:
    number: int
    path: Path


VISUAL_EXTENSIONS = frozenset({".pdf", ".docx"})
_PAGE_LOCATION = re.compile(r"^стр\.\s*(\d+)(?:\D|$)", flags=re.IGNORECASE)
_PAGE_FILE = re.compile(r"^page-(\d+)\.png$")


def document_has_visuals(path: Path) -> bool:
    suffix = path.suffix.casefold()
    if suffix == ".docx":
        with zipfile.ZipFile(path) as archive:
            return any(
                name.startswith("word/media/") and not name.endswith("/")
                for name in archive.namelist()
            )
    if suffix == ".pdf":
        from pypdf import PdfReader

        for page in PdfReader(path).pages:
            resources = _resolve_pdf_object(page.get("/Resources"))
            if not resources:
                continue
            xobjects = _resolve_pdf_object(resources.get("/XObject"))
            if not xobjects:
                continue
            for reference in xobjects.values():
                item = _resolve_pdf_object(reference)
                if item and str(item.get("/Subtype")) == "/Image":
                    return True
        return False
    return False


def render_document_pages(
    path: Path,
    output_dir: Path,
    *,
    dpi: int = 144,
    timeout_seconds: float = 120.0,
) -> tuple[RenderedPage, ...]:
    suffix = path.suffix.casefold()
    if suffix not in VISUAL_EXTENSIONS:
        raise VisualRenderingError(f"Рендер страниц для формата {suffix} не поддерживается")
    if dpi < 72 or dpi > 300:
        raise VisualRenderingError("DPI рендера должен быть от 72 до 300")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".visual-render-", dir=output_dir.parent) as temp:
        work_dir = Path(temp)
        staged_pages = work_dir / "pages"
        staged_pages.mkdir()
        source_pdf = path.resolve()
        if suffix == ".docx":
            source_pdf = _convert_docx_to_pdf(
                path.resolve(), work_dir, timeout_seconds=timeout_seconds
            )
        _render_pdf(
            source_pdf,
            staged_pages,
            dpi=dpi,
            timeout_seconds=timeout_seconds,
        )
        pages = _collect_pages(staged_pages)
        if not pages:
            raise VisualRenderingError("Рендер не создал ни одной страницы")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        staged_pages.replace(output_dir)

    return tuple(RenderedPage(page.number, output_dir / page.path.name) for page in pages)


def page_number_from_location(location: str) -> int | None:
    match = _PAGE_LOCATION.match(location.strip())
    return int(match.group(1)) if match else None


def page_image_path(document_path: Path, page_number: int) -> Path:
    if page_number < 1:
        raise ValueError("Номер страницы должен быть положительным")
    return document_path.parent / "pages" / f"page-{page_number}.png"


def _resolve_pdf_object(value: Any) -> Any:
    getter = getattr(value, "get_object", None)
    return getter() if callable(getter) else value


def _convert_docx_to_pdf(path: Path, work_dir: Path, *, timeout_seconds: float) -> Path:
    pdf_dir = work_dir / "pdf"
    home_dir = work_dir / "home"
    profile_dir = work_dir / "libreoffice-profile"
    pdf_dir.mkdir()
    home_dir.mkdir()
    profile_dir.mkdir()
    env = os.environ.copy()
    env.update({"HOME": str(home_dir), "TMPDIR": str(work_dir)})
    command = [
        "soffice",
        "--headless",
        f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
        "--convert-to",
        "pdf:writer_pdf_Export",
        "--outdir",
        str(pdf_dir),
        str(path),
    ]
    _run(command, timeout_seconds=timeout_seconds, env=env, tool="LibreOffice")
    candidates = tuple(pdf_dir.glob("*.pdf"))
    if len(candidates) != 1 or candidates[0].stat().st_size == 0:
        raise VisualRenderingError("LibreOffice не создал корректный PDF из DOCX")
    return candidates[0]


def _render_pdf(
    source_pdf: Path,
    pages_dir: Path,
    *,
    dpi: int,
    timeout_seconds: float,
) -> None:
    command = [
        "pdftoppm",
        "-png",
        "-r",
        str(dpi),
        str(source_pdf),
        str(pages_dir / "page"),
    ]
    _run(command, timeout_seconds=timeout_seconds, env=None, tool="Poppler")


def _run(
    command: list[str],
    *,
    timeout_seconds: float,
    env: dict[str, str] | None,
    tool: str,
) -> None:
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
    except FileNotFoundError as error:
        raise VisualRenderingError(f"Для рендера не найден {tool}") from error
    except subprocess.TimeoutExpired as error:
        raise VisualRenderingError(f"{tool} превысил лимит времени рендера") from error
    except subprocess.CalledProcessError as error:
        raise VisualRenderingError(f"{tool} не смог отрендерить документ") from error


def _collect_pages(directory: Path) -> tuple[RenderedPage, ...]:
    numbered: list[RenderedPage] = []
    for path in directory.glob("page-*.png"):
        match = _PAGE_FILE.match(path.name)
        if match and path.stat().st_size:
            numbered.append(RenderedPage(number=int(match.group(1)), path=path))
    numbered.sort(key=lambda page: page.number)
    expected = list(range(1, len(numbered) + 1))
    if [page.number for page in numbered] != expected:
        raise VisualRenderingError("Рендер создал непоследовательные номера страниц")
    staged: list[RenderedPage] = []
    for page in numbered:
        temporary = directory / f".normalized-page-{page.number}.png"
        page.path.replace(temporary)
        staged.append(RenderedPage(page.number, temporary))
    normalized: list[RenderedPage] = []
    for page in staged:
        target = directory / f"page-{page.number}.png"
        page.path.replace(target)
        normalized.append(RenderedPage(page.number, target))
    return tuple(normalized)
