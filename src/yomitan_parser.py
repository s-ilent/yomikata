"""Yomitan dictionary parser for ZIP format."""
import json
import zipfile
from collections.abc import Generator
from typing import Any


def _flatten_content(data, indent=0) -> str:
    """Recursively extract text from Yomitan structured-content objects with basic formatting."""
    if isinstance(data, str):
        return data

    if isinstance(data, list):
        items = []
        for item in data:
            flattened = _flatten_content(item, indent)
            if flattened:
                items.append(flattened)
        # Join with spaces for lists within a sense
        return " ".join(items)

    if isinstance(data, dict):
        tag = data.get("tag")

        # Handle Yomitan structured-content wrapper
        if data.get("type") == "structured-content":
            content = data.get("content", [])
            if isinstance(content, list):
                parts = []
                for c in content:
                    result = _flatten_content(c)
                    if result:
                        parts.append(result)
                return " | ".join(parts)  # Use | to separate different sections
            return _flatten_content(content)

        # Handle forms (spelling/reading variants table)
        if data.get("data", {}).get("content") == "forms":
            return _extract_forms(data.get("content", []))

        # Skip example sentences - they're too verbose
        if data.get("data", {}).get("content") == "example-sentence":
            return ""

        # If it's a glossary list, join items with ", " for clarity
        if data.get("data", {}).get("content") == "glossary":
            items = [_flatten_content(li) for li in data.get("content", [])]
            return ", ".join([i for i in items if i])

        # If it's a sense list, format as a numbered list
        if data.get("style", {}).get("listStyleType", "").startswith('"'):
            number = data["style"]["listStyleType"].strip('"').strip()
            # Get only the glossary, not extra-info
            content = data.get("content", [])
            glossary_text = ""
            for item in content:
                if isinstance(item, dict) and item.get("data", {}).get("content") == "glossary":
                    glossary_text = _flatten_content(item)
                    break
            return f"◆{number} {glossary_text}"

        # If it's a ruby tag, extract only the base text (index 0)
        if tag == "ruby" and isinstance(data.get("content"), list):
             return _flatten_content(data["content"][0])

        # If it's a structural tag we want to skip, recurse into content
        if tag in ["div", "span", "ul", "ol", "li", "a"]:
            return _flatten_content(data.get("content", ""))

        # Exclude technical types and attribution
        if tag is None and "type" in data:
            return " ".join([_flatten_content(v) for k, v in data.items() if k != "type" and isinstance(v, (str, list, dict))])
        if tag == "attribution":
            return ""

        # Otherwise just recurse on data values
        return " ".join([_flatten_content(v) for v in data.values() if isinstance(v, (str, list, dict))])

    return ""


def _extract_text_from_content(content) -> str:
    """Extract plain text from structured-content tree nodes."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(_extract_text_from_content(item) for item in content).strip()
    if isinstance(content, dict):
        if content.get("tag") == "ruby":
            # Extract only the base text (first child)
            ruby_content = content.get("content", [])
            if isinstance(ruby_content, list) and ruby_content:
                return _extract_text_from_content(ruby_content[0])
            return ""
        if content.get("tag") == "br":
            return "\n"
        if content.get("tag") in (
            "span", "div", "a", "li", "ol", "ul",
            "td", "th", "tr", "thead", "tbody", "tfoot", "table",
        ):
            return _extract_text_from_content(content.get("content", ""))
        # Skip images
        if content.get("tag") == "img":
            return ""
        # Fallback: recurse into dict values
        text = " ".join(
            _extract_text_from_content(v)
            for v in content.values()
            if isinstance(v, (str, list, dict))
        )
        return text.strip()
    return ""


def _parse_structured_glossary(data: dict) -> list[dict]:
    """Parse Yomitan structured-content format into sense list.

    Input: a {"type": "structured-content"} dict
    Output: [{"pos": ["noun", "uk"], "gloss": ["spring"]}, ...]

    Returns empty list if data is not structured-content or can't be parsed.
    """
    if not isinstance(data, dict) or data.get("type") != "structured-content":
        return []

    content = data.get("content")
    if content is None:
        return []

    # Handle case where content is a plain string (term_bank_1 style)
    if isinstance(content, str):
        return []

    # Handle case where content is a list of items
    if isinstance(content, list):
        # Quick check: no dict items with tag="ul" or "ol" means not a Jitendex-style structure
        has_structural_tag = any(
            isinstance(item, dict) and item.get("tag") in ("ul", "ol")
            for item in content
        )
        if not has_structural_tag:
            return []

        # Try each item - look for ul containers with list items
        for item in content:
            if isinstance(item, dict) and item.get("tag") == "ul":
                result = _parse_sense_group(item)
                if result:
                    return result
            elif isinstance(item, dict) and item.get("tag") == "ol":
                result = _parse_flat_senses(item)
                if result:
                    return result
        return []

    # Handle case where content is a single dict (term_bank_2 / Jitendex style)
    if isinstance(content, dict):
        if content.get("tag") == "ul":
            return _parse_sense_group(content)
        if content.get("tag") == "ol":
            return _parse_flat_senses(content)
        return []

    return []


def _parse_sense_group(ul_data: dict) -> list[dict]:
    """Parse a ul > li sense-group container from Jitendex format."""
    senses = []
    li_items = ul_data.get("content", [])

    if isinstance(li_items, dict):
        li_items = [li_items]

    if not isinstance(li_items, list):
        return []

    for li in li_items:
        if not isinstance(li, dict) or li.get("tag") != "li":
            continue

        # Skip non-glossary sections (forms, examples, etc.)
        li_data = li.get("data", {})
        if li_data.get("content") in ("forms",):
            continue

        # Collect POS tags from span.tag elements at this level
        pos_tags = _collect_pos_tags(li.get("content", []))

        # Find the ol containing numbered senses
        li_content = li.get("content", [])
        if isinstance(li_content, dict):
            li_content = [li_content]

        has_found_ol = False
        for child in li_content:
            if isinstance(child, dict) and child.get("tag") == "ol":
                has_found_ol = True
                # Parse the numbered senses within this ol
                ol_content = child.get("content", [])
                if isinstance(ol_content, dict):
                    ol_content = [ol_content]
                if isinstance(ol_content, list):
                    for sense_li in ol_content:
                        if isinstance(sense_li, dict) and sense_li.get("tag") == "li":
                            sense = _parse_single_sense(sense_li)
                            if sense:
                                # Merge with the group-level POS tags
                                if sense.get("pos"):
                                    # POS from sense level adds to group POS
                                    pass
                                else:
                                    sense["pos"] = pos_tags
                                senses.append(sense)

        # No ol found - this could be a single-sense group with just a glossary
        if not has_found_ol:
            glosses = _extract_glosses(li_content)
            if glosses:
                senses.append({"pos": pos_tags, "gloss": glosses})

    return senses


def _parse_flat_senses(ol_data: dict) -> list[dict]:
    """Parse an ol > li flat sense list (simpler format)."""
    senses = []
    ol_content = ol_data.get("content", [])
    if isinstance(ol_content, dict):
        ol_content = [ol_content]
    if not isinstance(ol_content, list):
        return []

    for li in ol_content:
        if not isinstance(li, dict) or li.get("tag") != "li":
            continue
        sense = _parse_single_sense(li)
        if sense:
            senses.append(sense)

    return senses


def _parse_single_sense(li_data: dict) -> dict | None:
    """Parse a single sense li, extracting glosses."""
    pos = _collect_pos_tags(li_data.get("content", []))

    content = li_data.get("content", [])
    if isinstance(content, dict):
        content = [content]
    if not isinstance(content, list):
        return None

    glosses = _extract_glosses(content)
    if not glosses:
        # Fallback: use text content
        text = _extract_text_from_content(content)
        if text.strip():
            glosses = [text.strip()]

    if glosses:
        return {"pos": pos, "gloss": glosses}
    return None


def _collect_pos_tags(content) -> list[str]:
    """Collect POS tag text from span[data.class="tag"] elements."""
    if not isinstance(content, list):
        if isinstance(content, dict):
            content = [content]
        else:
            return []

    tags = []
    for item in content:
        if isinstance(item, dict) and item.get("tag") == "span":
            item_data = item.get("data", {})
            if item_data.get("class") == "tag":
                tag_text = item.get("content", "")
                if isinstance(tag_text, str) and tag_text.strip():
                    tags.append(tag_text.strip())
    return tags


def _extract_glosses(content: list) -> list[str]:
    """Extract gloss text from ul[data.content="glossary"] elements."""
    glosses = []
    for item in content:
        if isinstance(item, dict) and item.get("tag") == "ul":
            ul_data = item.get("data", {})
            if ul_data.get("content") == "glossary":
                # Found a glossary list
                glossary_content = item.get("content", [])
                if isinstance(glossary_content, dict):
                    glossary_content = [glossary_content]
                if isinstance(glossary_content, list):
                    for gloss_li in glossary_content:
                        if isinstance(gloss_li, dict) and gloss_li.get("tag") == "li":
                            text = _extract_text_from_content(gloss_li.get("content", ""))
                            if text.strip():
                                glosses.append(text.strip())
    return glosses


def _safe_serialize(data) -> str:
    """Serialize structured Yomitan content to JSON string for DB storage."""
    try:
        return json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError, OverflowError):
        return json.dumps(str(data), ensure_ascii=False)


def _extract_forms(content) -> str:
    """Extract forms (spelling/reading variants) from table structure."""
    if not isinstance(content, list):
        return ""

    # Find the table
    table = None
    for item in content:
        if isinstance(item, dict) and item.get("tag") == "table":
            table = item.get("content", [])
            break

    if not table:
        return ""

    # Extract headers (kanji variants) from first row
    headers = []
    for row in table:
        if isinstance(row, dict) and row.get("data", {}).get("content") == "forms-header-row":
            for cell in row.get("content", []):
                if isinstance(cell, dict) and cell.get("tag") == "th":
                    text = _flatten_content(cell.get("content"))
                    if text:
                        headers.append(text)
            break

    if not headers:
        return ""

    # Extract data rows (readings + form types)
    form_rows = []
    for row in table:
        if isinstance(row, dict) and row.get("tag") == "tr" and row.get("data", {}).get("content") != "forms-header-row":
            cells = row.get("content", [])
            if not cells:
                continue

            # First cell is reading
            reading = _flatten_content(cells[0]) if cells else ""
            if not reading:
                continue

            # Rest are form types
            form_types = []
            for cell in cells[1:]:
                if isinstance(cell, dict):
                    cls = cell.get("data", {}).get("class", "")
                    if cls == "form-pri":
                        form_types.append("pri")
                    elif cls == "form-rare":
                        form_types.append("rare")
                    elif cls == "form-out":
                        form_types.append("obs")
                    else:
                        form_types.append(cls)

            # Match form types to headers
            forms = []
            for i, ft in enumerate(form_types):
                if i < len(headers):
                    if ft:  # Only include if there's a form type
                        marker = {"pri": "*", "rare": "?", "obs": "~"}.get(ft, "")
                        forms.append(f"{headers[i]}{marker}")
                    else:
                        forms.append(headers[i])  # Just the kanji if no marker

            if forms:
                form_rows.append(f"{reading}: {' '.join(forms)}")

    return " | ".join(form_rows) if form_rows else ""

def parse_yomitan_zip(zip_path: str) -> Generator[dict[str, Any]]:
    """Parse Yomitan ZIP file and yield dictionary entries.
    
    Yields dicts with keys: headword, reading, pos, pitch_accent, glossary, priority,
    dictionary_name, dictionary_meta
    """
    with zipfile.ZipFile(zip_path, 'r') as z:
        # Read metadata from index.json
        dict_meta = {}
        if 'index.json' in z.namelist():
            with z.open('index.json') as f:
                dict_meta = json.load(f)

        dict_name = dict_meta.get('title', 'Yomitan')

        # Find all term_bank, kanji_bank, term_meta_bank, and kanji_meta_bank files
        files = sorted([f for f in z.namelist() if any(x in f for x in ['term_bank', 'kanji_bank', 'term_meta_bank', 'kanji_meta_bank']) and f.endswith('.json')])

        for f_name in files:
            with z.open(f_name) as f:
                data = json.load(f)

                # Determine file type
                is_kanji = 'kanji_bank' in f_name
                is_meta = 'meta_bank' in f_name

                for item in data:
                    if is_meta:
                        # Meta bank schema (usually term/kanji, type, data)
                        # We currently store these as standard entries to be searchable or merged
                        headword = item[0]
                        glossary = ""
                        if len(item) > 2:
                            payload = item[2]
                            if isinstance(payload, dict):
                                glossary = str(payload.get('frequency') or payload.get('displayValue') or "")
                            else:
                                glossary = str(payload)

                        entry = {
                            'headword': headword,
                            'reading': "",
                            'pos': "meta",
                            'pitch_accent': "",
                            'glossary': glossary,
                            'priority': 0,
                            'dictionary_name': dict_name,
                            'dictionary_meta': dict_meta
                        }
                    elif is_kanji:
                        # Kanji bank schema: 0: kanji, 1: onyomi, 2: kunyomi, 3: tags, 4: meanings, 5: stats
                        headword = item[0]
                        reading = ""
                        pos = ", ".join(item[2]) if len(item) > 2 and isinstance(item[2], list) else str(item[2] if len(item) > 2 else "")
                        glossary = ""
                        if len(item) > 4 and item[4]:
                            glossary = " / ".join([_flatten_content(d) for d in item[4]]) if isinstance(item[4], list) else _flatten_content(item[4])

                        priority = 0
                        if len(item) > 5 and isinstance(item[5], dict):
                            priority = item[5].get('priority', 0)

                        entry = {
                            'headword': headword,
                            'reading': reading,
                            'pos': pos,
                            'pitch_accent': "",
                            'glossary': glossary,
                            'priority': priority,
                            'dictionary_name': dict_name,
                            'dictionary_meta': dict_meta
                        }
                    else:
                        # Term bank schema: 0: kanji, 1: reading, 2: pos_tags, 3: rules, 4: score, 5: definitions
                        headword = item[0]
                        reading = item[1] if len(item) > 1 else ""
                        pos = ", ".join(item[2]) if len(item) > 2 and isinstance(item[2], list) else str(item[2] if len(item) > 2 else "")
                        glossary = ""
                        if len(item) > 5 and item[5]:
                            defs = item[5]
                            glossary = _safe_serialize(defs) if isinstance(defs, (list, dict)) else str(defs)
                        priority = item[4] if len(item) > 4 else 0

                        entry = {
                            'headword': headword,
                            'reading': reading,
                            'pos': pos,
                            'pitch_accent': "",
                            'glossary': glossary,
                            'priority': priority,
                            'dictionary_name': dict_name,
                            'dictionary_meta': dict_meta
                        }
                    yield entry
