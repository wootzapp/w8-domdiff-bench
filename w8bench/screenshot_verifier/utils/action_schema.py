"""Recorded browser-action arguments used only by failure diagnostics."""

# These annotate a recorded action; they are not parameters passed to a tool.
# Ignore them only when checking invocation keys, never in judge action history.
ACTION_METADATA_KEYS = frozenset({"thoughts", "target"})

FARA_ACTION_DEFINITIONS: dict[str, set[str]] = {
    "key": {"keys", "key"},
    "type": {"text", "coordinate", "ref", "press_enter", "delete_existing_text"},
    "mouse_move": {"coordinate"},
    "left_click": {"coordinate", "ref"},
    "scroll": {"coordinate", "pixels", "ref"},
    "select": {"ref", "text"},
    "visit_url": {"url"},
    "web_search": {"query"},
    "history_back": set(),
    "pause_and_memorize_fact": {"fact"},
    "wait": {"time", "seconds"},
    "terminate": {"status"},
}
