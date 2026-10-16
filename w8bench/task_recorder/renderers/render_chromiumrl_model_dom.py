#!/usr/bin/env python3
"""Render ChromiumRL.getModelDOM's structured JSON response as model text.

Blink owns all evidence selection, grouping, normalization, and ordering. This
host renderer deliberately performs only validation and deterministic section
joining; it does not inspect dom.json and it applies no caps or filtering.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


RENDERER_NAME = "chromiumrl-model-dom"
SECTION_ORDER = (
    "header",
    "tables",
    "content",
    "media",
    "actions",
    "scroll_regions",
)


class ModelDOMRenderError(ValueError):
    """Raised when browser-produced model-DOM JSON violates its contract."""


def model_dom_from_envelope(payload: Any) -> dict[str, Any]:
    """Extract the modelDOM object from the capture-style result envelope."""
    if not isinstance(payload, dict) or set(payload) != {"result"}:
        raise ModelDOMRenderError("expected a single-key result envelope")
    result = payload.get("result")
    if not isinstance(result, dict) or set(result) != {"modelDOM"}:
        raise ModelDOMRenderError("expected result.modelDOM and no unknown fields")
    model_dom = result.get("modelDOM")
    if not isinstance(model_dom, dict):
        raise ModelDOMRenderError("result.modelDOM must be an object")
    return model_dom


def render_model_dom(model_dom: dict[str, Any]) -> str:
    """Validate and join one structured browser-produced model projection."""
    unknown = set(model_dom) - {"rendererName", "sections"}
    if unknown:
        raise ModelDOMRenderError(
            f"unknown modelDOM fields: {', '.join(sorted(unknown))}"
        )
    name = model_dom.get("rendererName")
    if name != RENDERER_NAME:
        raise ModelDOMRenderError(
            f"unexpected rendererName: {name!r}; expected {RENDERER_NAME!r}"
        )
    sections = model_dom.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ModelDOMRenderError("modelDOM.sections must be a non-empty array")

    order_index = {name: index for index, name in enumerate(SECTION_ORDER)}
    seen: set[str] = set()
    previous_index = -1
    rendered_sections: list[str] = []
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise ModelDOMRenderError(f"sections[{index}] must be an object")
        unknown_section = set(section) - {"name", "lines"}
        if unknown_section:
            raise ModelDOMRenderError(
                f"unknown sections[{index}] fields: "
                f"{', '.join(sorted(unknown_section))}"
            )
        name = section.get("name")
        if not isinstance(name, str) or name not in order_index:
            raise ModelDOMRenderError(f"invalid sections[{index}].name: {name!r}")
        if name in seen:
            raise ModelDOMRenderError(f"duplicate modelDOM section: {name}")
        if order_index[name] <= previous_index:
            raise ModelDOMRenderError("modelDOM sections are out of canonical order")
        seen.add(name)
        previous_index = order_index[name]
        lines = section.get("lines")
        if (
            not isinstance(lines, list)
            or not lines
            or any(not isinstance(line, str) for line in lines)
        ):
            raise ModelDOMRenderError(
                f"sections[{index}].lines must be a non-empty string array"
            )
        rendered_sections.append("\n".join(lines))

    if sections[0].get("name") != "header":
        raise ModelDOMRenderError("the first modelDOM section must be header")
    return "\n\n".join(rendered_sections).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Browser-produced dom_model.json")
    parser.add_argument("-o", "--output", type=Path, help="Optional output TXT path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    rendered = render_model_dom(model_dom_from_envelope(payload))
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        try:
            sys.stdout.write(rendered)
        except BrokenPipeError:
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
