"""Yomitan dictionary parser for ZIP format."""
import json
import zipfile
from typing import Generator, Dict, Any


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

def parse_yomitan_zip(zip_path: str) -> Generator[Dict[str, Any], None, None]:
    """Parse Yomitan ZIP file and yield dictionary entries.
    
    Yields dicts with keys: headword, reading, pos, pitch_accent, glossary, priority
    """
    with zipfile.ZipFile(zip_path, 'r') as z:
        # Find all term_bank_*.json files
        term_files = sorted([f for f in z.namelist() if 'term_bank' in f and f.endswith('.json')])
        
        for f_name in term_files:
            with z.open(f_name) as f:
                data = json.load(f)
                for item in data:
                    # Yomitan schema:
                    # 0: kanji, 1: reading, 2: pos_tags, 3: rules, 4: score, 
                    # 5: definitions, 6: sequence, 7: tags
                    headword = item[0]
                    reading = item[1] if len(item) > 1 else ""
                    
                    # Convert pos_tags list to string
                    pos = ""
                    if len(item) > 2 and item[2]:
                        if isinstance(item[2], list):
                            pos = ", ".join(item[2])
                        else:
                            pos = str(item[2])
                    
                    # Handle definitions (can be list, string, or structured-content dict)
                    glossary = ""
                    if len(item) > 5 and item[5]:
                        defs = item[5]
                        if isinstance(defs, list):
                            glossary = " / ".join([_flatten_content(d) for d in defs])
                        elif isinstance(defs, dict):
                            glossary = _flatten_content(defs)
                        else:
                            glossary = str(defs)
                    
                    priority = item[4] if len(item) > 4 else 0
                    
                    yield {
                        'headword': headword,
                        'reading': reading,
                        'pos': pos,
                        'pitch_accent': "",
                        'glossary': glossary,
                        'priority': priority,
                        'dictionary_name': 'Yomitan'
                    }
