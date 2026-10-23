from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

HEADER_MIN_Y = 580.0
FOOTER_MAX_Y = 25.0
HEADING_INDENT_TOLERANCE = 6.0

MAIN_ARTICLE = re.compile(r"^(\d{1,2})\.\s+([A-Z][^a-z]{2,})$")
SUB_ARTICLE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,3})\.?\s+(\S.{0,110})$")
APPENDIX = re.compile(r"^APPENDIX\s+(\d{1,2})\s*[:\-–]\s*(.+)$")
TOC_ENTRY = re.compile(r"\s\d{1,3}$")
DATES = re.compile(r"published on:\s*(\d{2}\.\d{2}\.\d{4}).*application from:\s*(\d{2}\.\d{2}\.\d{4})")


@dataclass(frozen=True)
class Line:
    page: int
    x: float
    y: float
    text: str


def english_lines(pdf_path: str | Path) -> list[Line]:
    """Body lines from the right-hand (English) column of the bilingual regulation PDFs, top to bottom."""
    import pypdf

    lines = []
    for page_number, page in enumerate(pypdf.PdfReader(str(pdf_path)).pages, start=1):
        middle = float(page.mediabox.width) / 2
        pieces: dict[float, list[tuple[float, str]]] = {}

        def visit(text, cm, tm, font_dict, font_size):
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            if text.strip() and x >= middle - 5 and FOOTER_MAX_Y < y < HEADER_MIN_Y:
                pieces.setdefault(round(y, 1), []).append((x, text))

        page.extract_text(visitor_text=visit)
        for y in sorted(pieces, reverse=True):
            row = sorted(pieces[y])
            lines.append(Line(page_number, row[0][0], y, "".join(text for _, text in row).strip()))
    return lines


def publication_dates(pdf_path: str | Path) -> dict[str, str]:
    import pypdf

    match = DATES.search(pypdf.PdfReader(str(pdf_path)).pages[0].extract_text())
    return {"published": match.group(1), "effective_from": match.group(2)} if match else {}


def is_contents_page(page_lines: list[Line]) -> bool:
    """A table-of-contents page: most lines end in a page number."""
    return len(page_lines) >= 5 and sum(bool(TOC_ENTRY.search(line.text)) for line in page_lines) > 0.6 * len(page_lines)


def chunk_lines(lines: list[Line], metadata: dict) -> list[dict]:
    """One chunk per lowest-level numbered heading, each carrying the headings above it and its pages.

    Main articles must follow in sequence (1, 2, 3...). A sub-heading only counts if it starts at the
    column's left edge and belongs to the current article, so numbers inside a sentence don't open a chunk.
    Inside an appendix, its own numbered headings become chunks such as `APPENDIX 7/1.1`.
    """
    by_page: dict[int, list[Line]] = {}
    for line in lines:
        by_page.setdefault(line.page, []).append(line)
    body = [line for page in sorted(by_page) if not is_contents_page(by_page[page]) for line in by_page[page]]
    if not body:
        return []
    left_edge = min(line.x for line in body)

    chunks: list[dict] = []
    section: tuple[str, str] | None = None
    headings: dict[str, str] = {}
    appendix: str | None = None
    current: dict | None = None

    def close():
        if not current or not current["lines"]:
            return
        number = current["number"]
        path = [f"{section[0]} {section[1]}"] if section else []
        path += [f"{key} {headings[key]}" for key in sorted(headings, key=_sort_key)
                 if number == key or number.startswith(key + ".")]
        article = f"APPENDIX {appendix}/{number}" if appendix and number else (f"APPENDIX {appendix}" if appendix else number)
        chunks.append({
            **metadata,
            "chunk_id": f"{metadata['document_id']}:{article}",
            "article": article,
            "heading": current["heading"],
            "path": " > ".join(path),
            "page_start": current["page_start"],
            "page_end": current["page_end"],
            "text": " ".join([" > ".join(path)] + current["lines"]),
        })

    def start(number: str, heading: str, page: int) -> dict:
        return {"number": number, "heading": heading, "page_start": page, "page_end": page, "lines": []}

    main_number = 0
    for line in body:
        at_edge = line.x <= left_edge + HEADING_INDENT_TOLERANCE
        appendix_match = APPENDIX.match(line.text)
        main = MAIN_ARTICLE.match(line.text)
        sub = SUB_ARTICLE.match(line.text) if at_edge else None
        top = sub.group(1).split(".")[0] if sub else None

        if appendix_match:
            close()
            appendix, headings, main_number = appendix_match.group(1), {}, 0
            section = (f"APPENDIX {appendix}:", appendix_match.group(2).strip())
            current = start("", section[1], line.page)
        elif main and appendix is None and int(main.group(1)) == main_number + 1:
            close()
            main_number, headings = int(main.group(1)), {}
            section = (f"{main_number}.", main.group(2).strip())
            current = start(str(main_number), section[1], line.page)
        elif main and appendix is not None and at_edge:
            close()
            headings = {main.group(1): main.group(2).strip()}
            current = start(main.group(1), main.group(2).strip(), line.page)
        elif sub and sub.group(1) not in headings and (
            (appendix is None and top == str(main_number)) or appendix is not None
        ):
            close()
            headings[sub.group(1)] = sub.group(2).strip()
            current = start(sub.group(1), sub.group(2).strip(), line.page)
        elif current is not None:
            current["lines"].append(line.text)
            current["page_end"] = line.page
    close()
    return chunks


def _sort_key(article: str) -> tuple[int, ...]:
    return tuple(int(part) for part in article.split("."))


def build_chunks(manifest_path: str | Path, output_path: str | Path) -> list[dict]:
    """Chunk every regulation in the download manifest and write them as JSON lines."""
    manifest_path = Path(manifest_path)
    chunks = []
    for document in json.loads(manifest_path.read_text()):
        pdf = manifest_path.parent / document["file"]
        metadata = {
            "document_id": document["document_id"],
            "title": document["title"],
            "season": document["season"],
            "revision": document["revision"],
            "source_url": document["url"],
            "sha256": document["sha256"],
            **publication_dates(pdf),
        }
        chunks += chunk_lines(english_lines(pdf), metadata)
    Path(output_path).write_text("".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks))
    return chunks
