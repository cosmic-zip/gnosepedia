#!/usr/bin/env python3
"""Split 'PARTE *.md' files from Grimore/ by H2 (##) sections into uploads/grimorie/."""

from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "Grimore"
OUT_DIR = ROOT / "uploads" / "grimorie"

H2_RE = re.compile(r"^##\s+(.+?)\s*$")
H1_RE = re.compile(r"^#\s+")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def sanitize_filename(title: str) -> str:
    """Clean invalid filesystem characters from a heading while keeping symbols like ⛥."""
    name = title.strip()
    name = re.sub(r'[\\/:*?"<>|]+', " - ", name)
    name = re.sub(r"\s+", " ", name).strip(" .-")
    return name or "Sem título"


def unique_path(folder: Path, base_name: str) -> Path:
    """Ensure no filename collision inside the same folder."""
    candidate = folder / f"{base_name}.md"
    counter = 2
    while candidate.exists():
        candidate = folder / f"{base_name} ({counter}).md"
        counter += 1
    return candidate


def split_markdown_by_h2(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (intro_content, [(section_title, section_content), ...])."""
    lines = text.splitlines(keepends=True)
    intro_lines: list[str] = []
    sections: list[tuple[str, list[str]]] = []

    in_code_block = False
    fence_char = ""

    for line in lines:
        fence_match = FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if not in_code_block:
                in_code_block = True
                fence_char = marker[0]
            elif marker[0] == fence_char:
                in_code_block = False
                fence_char = ""

        if not in_code_block:
            h2_match = H2_RE.match(line)
            if h2_match:
                sections.append((h2_match.group(1), [line]))
                continue

        if sections:
            sections[-1][1].append(line)
        else:
            intro_lines.append(line)

    intro_text = "".join(intro_lines).strip()
    parsed_sections = [(title, "".join(sec_lines).strip() + "\n") for title, sec_lines in sections]
    return intro_text, parsed_sections


def has_non_h1_content(intro_text: str) -> bool:
    for line in intro_text.splitlines():
        if line.strip() and not H1_RE.match(line):
            return True
    return False


def main() -> None:
    if not SRC_DIR.is_dir():
        raise SystemExit(f"Source directory not found: {SRC_DIR}")

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    parte_files = sorted(SRC_DIR.glob("PARTE *.md"))
    total_files_written = 0

    for md_file in parte_files:
        folder = OUT_DIR / md_file.stem
        folder.mkdir(parents=True, exist_ok=True)

        raw = md_file.read_text(encoding="utf-8")
        intro_text, sections = split_markdown_by_h2(raw)

        if not sections:
            out_path = folder / md_file.name
            out_path.write_text(raw, encoding="utf-8")
            total_files_written += 1
            print(f"[NO-H2] {md_file.name} -> {out_path.relative_to(OUT_DIR)}")
            continue

        if intro_text and has_non_h1_content(intro_text):
            intro_path = unique_path(folder, "Introdução")
            intro_path.write_text(intro_text + "\n", encoding="utf-8")
            total_files_written += 1

        for title, content in sections:
            clean_name = sanitize_filename(title)
            out_path = unique_path(folder, clean_name)
            out_path.write_text(content, encoding="utf-8")
            total_files_written += 1

        print(f"[SPLIT] {md_file.name} -> {len(sections)} seções (+{'intro' if (intro_text and has_non_h1_content(intro_text)) else 'sem intro'})")

    print(f"\nConcluído: {len(parte_files)} pastas criadas, {total_files_written} arquivos gerados em {OUT_DIR}")


if __name__ == "__main__":
    main()
