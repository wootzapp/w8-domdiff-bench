"""Canonical Microsoft/FARA action argument schema used by failure analysis."""

FARA_ACTION_DEFINITIONS: dict[str, set[str]] = {
    "key": {"keys"},
    "type": {"text", "coordinate", "press_enter", "delete_existing_text"},
    "mouse_move": {"coordinate"},
    "left_click": {"coordinate"},
    "scroll": {"coordinate", "pixels"},
    "visit_url": {"url"},
    "web_search": {"query"},
    "history_back": set(),
    "pause_and_memorize_fact": {"fact"},
    "wait": {"time"},
    "terminate": {"status"},
}
