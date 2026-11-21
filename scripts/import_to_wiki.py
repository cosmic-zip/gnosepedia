#!/usr/bin/env python3
"""Import Markdown folder hierarchy from uploads/grimorie/ into Feather Wiki (app/index.html)."""

from pathlib import Path
import json
import random
import re
import string
import time

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "uploads" / "grimorie"
WIKI_HTML = ROOT / "index.html"

SCRIPT_P_RE = re.compile(
    r'(<script\s+id="?p"?\s+type="?application/json"?>)(.*?)(</script>)',
    re.DOTALL,
)

ROMAN_MAP = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def roman_to_int(s: str) -> int:
    total = 0
    prev = 0
    for ch in reversed(s.upper()):
        val = ROMAN_MAP.get(ch, 0)
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    return total


def folder_sort_key(path: Path) -> tuple[int, str]:
    m = re.match(r"^PARTE\s+([IVXLC]+)\b", path.name, re.IGNORECASE)
    if m:
        return (roman_to_int(m.group(1)), path.name.lower())
    return (9999, path.name.lower())


def fw_slug(text: str) -> str:
    """Exact equivalent of Feather Wiki's FW.slug."""
    s = text.lower()
    s = re.sub(r"\s", "_", s)
    s = re.sub(r"[\x00-\x2F\x3A-\x40\[\\\]^`\x7B-\x7F]", "-", s)
    return s


def fw_decompress(data: dict) -> dict:
    """Exact equivalent of Feather Wiki's FW.json.decompress for root object."""
    if not isinstance(data, dict) or "_" not in data:
        return data
    mapping = data.pop("_")
    raw = json.dumps(data, ensure_ascii=False)
    for short_key, full_key in mapping.items():
        raw = re.sub(r'(?:"' + re.escape(short_key) + r'"):', f'"{full_key}":', raw)
    return json.loads(raw)


def gen_id(existing_ids: set[str]) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        candidate = "".join(random.choices(alphabet, k=9))
        if candidate not in existing_ids:
            existing_ids.add(candidate)
            return candidate


def unique_slug(base: str, existing_slugs: set[str]) -> str:
    candidate = base
    n = 1
    while candidate in existing_slugs:
        candidate = f"{base}_{n}"
        n += 1
    existing_slugs.add(candidate)
    return candidate


def main() -> None:
    if not SRC_DIR.is_dir():
        raise SystemExit(f"Source directory not found: {SRC_DIR}")
    if not WIKI_HTML.is_file():
        raise SystemExit(f"Wiki HTML not found: {WIKI_HTML}")

    html = WIKI_HTML.read_text(encoding="utf-8")
    match = SCRIPT_P_RE.search(html)
    if not match:
        raise SystemExit('Could not find <script id="p" type="application/json"> in app/index.html')

    raw_json = match.group(2).strip()
    wiki = fw_decompress(json.loads(raw_json)) if raw_json and raw_json != "{}" else {}
    wiki.setdefault("name", "Gnosepedia")
    wiki.setdefault("desc", "")
    wiki.setdefault("pages", [])
    wiki.setdefault("img", {})

    pages: list[dict] = wiki["pages"]
    existing_ids = {p["id"] for p in pages if "id" in p}
    existing_slugs = {p["slug"] for p in pages if "slug" in p}

    # Index existing pages by (name, parent) for idempotent re-runs
    by_key: dict[tuple[str, str], dict] = {
        (p.get("name", ""), p.get("parent", "")): p for p in pages
    }

    now = int(time.time() * 1000)
    folders = sorted((p for p in SRC_DIR.iterdir() if p.is_dir()), key=folder_sort_key)

    created = 0
    updated = 0

    for folder in folders:
        folder_name = folder.name
        folder_key = (folder_name, "")

        if folder_key in by_key:
            parent_page = by_key[folder_key]
            parent_page["md"] = now
            updated += 1
        else:
            parent_id = gen_id(existing_ids)
            parent_slug = unique_slug(fw_slug(folder_name), existing_slugs)
            parent_page = {
                "id": parent_id,
                "name": folder_name,
                "slug": parent_slug,
                "cd": now,
                "md": now,
                "editor": "md",
            }
            pages.append(parent_page)
            by_key[folder_key] = parent_page
            created += 1

        parent_id = parent_page["id"]

        # Put Introdução.md first if present, then alphabetical
        md_files = sorted(
            folder.glob("*.md"),
            key=lambda p: (0 if p.stem.lower() == "introdução" else 1, p.stem.lower()),
        )

        for md_file in md_files:
            title = md_file.stem
            content = md_file.read_text(encoding="utf-8")
            child_key = (title, parent_id)

            if child_key in by_key:
                child_page = by_key[child_key]
                child_page["content"] = content
                child_page["editor"] = "md"
                child_page["md"] = now
                updated += 1
            else:
                child_id = gen_id(existing_ids)
                child_slug = unique_slug(fw_slug(title), existing_slugs)
                child_page = {
                    "id": child_id,
                    "name": title,
                    "slug": child_slug,
                    "content": content,
                    "parent": parent_id,
                    "cd": now,
                    "md": now,
                    "editor": "md",
                }
                pages.append(child_page)
                by_key[child_key] = child_page
                created += 1

    # Feather Wiki's FW.json.decompress expects a "_" key map (empty dict = no renaming)
    wiki["_"] = {}
    serialized = json.dumps(wiki, ensure_ascii=False, separators=(",", ":"))
    serialized = serialized.replace("</script", "<\\/script")

    new_html = html[: match.start(2)] + serialized + html[match.end(2) :]
    WIKI_HTML.write_text(new_html, encoding="utf-8")

    print(
        f"Importação concluída em {WIKI_HTML}:\n"
        f"  Pastas (parent pages): {len(folders)}\n"
        f"  Criadas: {created} | Atualizadas: {updated} | Total de páginas na wiki: {len(pages)}\n"
        f"  Tamanho do JSON: {len(serialized):,} bytes"
    )


if __name__ == "__main__":
    main()
