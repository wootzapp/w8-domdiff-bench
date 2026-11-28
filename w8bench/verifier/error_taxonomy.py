"""Mode-bound taxonomy sections and string.Template escaping."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_CATEGORY_HEADING_RE = re.compile(r"^## (\d+)\.\s")
_SUMMARY_TABLE_RE = re.compile(r"^## Summary Decision Table", re.MULTILINE)
_SEPARATOR_RE = re.compile(r"^---\s*$", re.MULTILINE)


def _load_raw_md(resource_root: Path) -> str:
    return (resource_root / "resources" / "error_taxonomy_analysis.md").read_text(encoding="utf-8")


def escape_for_template(text: str) -> str:
    """Escape dollar signs before embedding text in string.Template."""
    return text.replace('$', '$$')


def _split_into_categories(md_text: str) -> dict[int, str]:
    """Read numbered category headings through the next category or summary boundary."""
    categories: dict[int, str] = {}
    lines = md_text.splitlines(keepends=True)
    current_cat: int | None = None
    current_lines: list[str] = []
    for line in lines:
        m = _CATEGORY_HEADING_RE.match(line)
        if m:
            if current_cat is not None:
                categories[current_cat] = ''.join(current_lines).rstrip('\n')
            current_cat = int(m.group(1))
            current_lines = [line]
            continue
        if _SUMMARY_TABLE_RE.match(line) or (_SEPARATOR_RE.match(line) and current_cat is not None):
            if current_cat is not None:
                categories[current_cat] = ''.join(current_lines).rstrip('\n')
                current_cat = None
                current_lines = []
            continue
        if current_cat is not None:
            current_lines.append(line)
    if current_cat is not None:
        categories[current_cat] = ''.join(current_lines).rstrip('\n')
    return categories


@lru_cache(maxsize=None)
def _failure_categories(resource_root: Path) -> str:
    cats = _split_into_categories(_load_raw_md(resource_root))
    return "\n\n".join(cats[index] for index in range(1, 7) if index in cats)


@lru_cache(maxsize=None)
def _failure_summary(resource_root: Path) -> str:
    md_text = _load_raw_md(resource_root)
    match = _SUMMARY_TABLE_RE.search(md_text)
    if not match:
        raise ValueError("Summary Decision Table not found in taxonomy .md")
    table_text = md_text[match.start():].rstrip("\n")
    kept = []
    for line in table_text.splitlines():
        if line.startswith("|:") or line.startswith("| Error Code"):
            kept.append(line)
            continue
        match = re.match(r"\|\s*(\d+)\.", line)
        if match:
            category = int(match.group(1))
            if 1 <= category <= 6:
                kept.append(line)
        elif line.startswith("## Summary"):
            kept.append(line)
    return "\n".join(kept)


def _postprocess_category_6_for_prompt(text: str) -> str:
    """Bind category 6 action-space and action-definition Template variables."""
    text = re.sub("The agent's action space includes GUI actions \\([^)]+\\), browser navigation \\([^)]+\\), and utility actions \\([^)]+\\)\\.", "The agent's action space is: [$action_space].", text)
    text = re.sub('(\\*\\*6\\.1 Invalid invocation\\*\\*.*?)((?=\\n- \\*\\*6\\.2))', '\\1 The valid actions and their accepted arguments are:\\n$action_definitions_text\\n', text, flags=re.DOTALL)
    return text


@lru_cache(maxsize=None)
def get_taxonomy_for_failure_prompt(resource_root: Path) -> tuple[str, str]:
    """Return escaped categories 1–6 and summary, with runtime action variables."""
    cats_text = _failure_categories(resource_root)
    summary = _failure_summary(resource_root)
    cats_escaped = escape_for_template(cats_text)
    summary_escaped = escape_for_template(summary)
    cats_escaped = _postprocess_category_6_for_prompt(cats_escaped)
    cats_escaped = re.sub('^## (\\d+\\.)', '### \\1', cats_escaped, flags=re.MULTILINE)
    calibration = 'Each top-level category contains numbered sub-categories, with an "Other" catch-all for errors \\\nthat don\'t fit existing sub-categories.\n\n**Calibration:** Not every imperfection is a failure. Only flag issues that materially affected \\\ntask completion, correctness, or user trust. Do not over-classify minor or cosmetic \\\ndiscrepancies as errors. When in doubt, err on the side of not flagging.'
    cats_final = calibration + '\n\n' + cats_escaped
    return (cats_final, summary_escaped)


def extract_subcategory_bullets(resource_root: Path, category_num: int) -> str:
    """Return raw numbered subcategory bullets for one category."""
    md = _load_raw_md(resource_root)
    cats = _split_into_categories(md)
    if category_num not in cats:
        raise ValueError(f'Category {category_num} not found in taxonomy .md')
    text = cats[category_num]
    bullets = []
    for line in text.splitlines():
        if re.match('^- \\*\\*\\d+\\.\\d+', line):
            bullets.append(line)
    return '\n'.join(bullets)
