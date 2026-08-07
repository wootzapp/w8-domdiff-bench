
#!/usr/bin/env python3
import gzip, json, re, zlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
TASKS = ROOT / "tasks"
OUT = ROOT
RAW_OUT = ROOT / "raw_captures"
SIM_OUT = ROOT / "structured_simulated"

TEXT_CAP_DIRECT = 240
TEXT_CAP_SUBTREE = 500
TEXT_BUDGET = 24000
NODE_CAP = 700
ATTR_ALLOW = {"role","href","src","alt","title","name","type","placeholder","datetime","value"}
DECORATIVE = {"script","style","noscript","template","head","meta","link","title",
              "path","rect","g","circle","ellipse","line","polyline","polygon","use","defs","clippath","mask","pattern","tspan"}
MEANINGFUL = {"html","body","main","article","section","nav","header","footer","form","ul","ol","li","table","tr","td","th","time","label","img","p","h1","h2","h3","h4","h5","h6","div"}
BOUNDARY_ROLES = {"main","article","list","listitem","row","cell","gridcell","table","navigation","banner","contentinfo","form","dialog","button","link","textbox","checkbox","radio","combobox","option"}
INTERACTIVE_TAGS = {"a","button","input","select","textarea","summary","option"}
INTERACTIVE_ROLES = {"button","link","checkbox","radio","tab","menuitem","combobox","searchbox","textbox","option"}

FACTS = {
    "book_title": "In a Dark, Dark Wood",
    "price": "£19.63",
    "availability": "In stock (18 available)",
    "star_rating_actual": "star-rating One",
    "star_rating_user_example": "star-rating Three",
    "form_value": "wrong",
    "post_submit_text": "Logout",
}
STOP_WORDS = {"the","a","an","and","or","to","of","in","on","with","for","shown","page","text"}


def load_json_gz(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def write_json_gz(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as f:
        json.dump(value, f, ensure_ascii=False, separators=(",", ":"))


def compact_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def gz_size(value: Any) -> int:
    return len(gzip.compress(compact_bytes(value), compresslevel=6))


def norm_text(s: Any) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()


def attrs_map(attrs: Any) -> dict[str, str]:
    out = {}
    if isinstance(attrs, dict):
        return {str(k): str(v) for k, v in attrs.items() if v is not None}
    if isinstance(attrs, list):
        if attrs and all(isinstance(x, dict) for x in attrs):
            for a in attrs:
                if "name" in a:
                    out[str(a.get("name"))] = str(a.get("value", ""))
        else:
            for i in range(0, len(attrs)-1, 2):
                out[str(attrs[i])] = str(attrs[i+1])
    return out


def node_tag(n: dict) -> str:
    return str(n.get("tagName") or n.get("tag") or "").lower()


def node_text_save(n: dict) -> str:
    return norm_text(n.get("textContent") or n.get("text") or "")


def bounds_box(n: dict) -> dict:
    b = n.get("bounds") or {}
    return b if isinstance(b, dict) else {}


def has_box(n: dict) -> bool:
    b = bounds_box(n)
    def f(k):
        try: return float(b.get(k, 0) or 0)
        except Exception: return 0.0
    return f("width") > 0 and f("height") > 0


def key_style(n: dict, k: str) -> str:
    ks = n.get("keyStyles") or n.get("style") or {}
    if isinstance(ks, dict):
        return str(ks.get(k, ""))
    return ""


def is_hidden(n: dict, attrs: dict[str,str]) -> bool:
    if attrs.get("aria-hidden", "").lower() == "true":
        return True
    if n.get("isVisible") is False:
        return True
    display = key_style(n, "display").lower()
    visibility = key_style(n, "visibility").lower()
    opacity = key_style(n, "opacity")
    if display == "none":
        return True
    if visibility and visibility != "visible":
        return True
    try:
        if opacity != "" and float(opacity) <= 0.01:
            return True
    except Exception:
        pass
    return False


def is_interactive(n: dict, attrs: dict[str,str]) -> bool:
    tag = node_tag(n)
    role = attrs.get("role", "").lower()
    if tag in INTERACTIVE_TAGS:
        if tag == "a" and not attrs.get("href"):
            return False
        return True
    if role in INTERACTIVE_ROLES:
        return True
    if attrs.get("onclick") or attrs.get("tabindex") not in (None, "", "-1"):
        return True
    if attrs.get("contenteditable", "").lower() in ("", "true") and "contenteditable" in attrs:
        return True
    return False


def is_scrollable(n: dict) -> bool:
    overflow = (key_style(n, "overflow") + " " + key_style(n, "overflowY") + " " + key_style(n, "overflowX")).lower()
    return any(x in overflow for x in ("auto", "scroll"))


def direct_text(n: dict, children: dict[int, list[dict]]) -> str:
    tag = node_tag(n)
    if tag in ("#text", "text"):
        return norm_text(n.get("textContent") or n.get("nodeValue") or "")[:TEXT_CAP_DIRECT]
    parts = []
    for c in children.get(int(n.get("nodeId", -1)), []):
        if node_tag(c) in ("#text", "text"):
            t = norm_text(c.get("textContent") or c.get("nodeValue") or "")
            if t:
                parts.append(t)
    return norm_text(" ".join(parts))[:TEXT_CAP_DIRECT]


def subtree_text(n: dict, children: dict[int, list[dict]], cap: int = TEXT_CAP_SUBTREE) -> str:
    tag = node_tag(n)
    if tag in ("#text", "text"):
        return norm_text(n.get("textContent") or n.get("nodeValue") or "")[:cap]
    out = []
    total = 0
    stack = list(children.get(int(n.get("nodeId", -1)), []))
    while stack and total < cap:
        cur = stack.pop(0)
        ctag = node_tag(cur)
        if ctag in {"script", "style", "noscript", "template"}:
            continue
        if ctag in ("#text", "text"):
            t = norm_text(cur.get("textContent") or cur.get("nodeValue") or "")
            if t:
                take = t[:max(0, cap-total)]
                out.append(take)
                total += len(take) + 1
        else:
            stack[0:0] = children.get(int(cur.get("nodeId", -1)), [])
    return norm_text(" ".join(out))[:cap]


def selected_attrs(attrs: dict[str,str]) -> list[dict[str,str]]:
    out = []
    for k, v in attrs.items():
        lk = k.lower()
        if lk in ATTR_ALLOW or lk.startswith("aria-"):
            if lk == "value" and attrs.get("type", "").lower() == "password":
                continue
            out.append({"name": k, "value": norm_text(v)[:160]})
        if len(out) >= 12:
            break
    return out


def node_states(n: dict, attrs: dict[str,str]) -> list[dict[str,Any]]:
    checks = {
        "expanded": "aria-expanded", "selected": "aria-selected", "disabled": "disabled",
        "required": "required", "readonly": "readonly", "checked": "checked",
    }
    out = []
    for name, attr in checks.items():
        if attr in attrs:
            val = attrs.get(attr)
            out.append({"name": name, "value": False if str(val).lower() == "false" else True})
    if attrs.get("contenteditable", "").lower() in ("", "true") and "contenteditable" in attrs:
        out.append({"name":"editable", "value": True})
    return out


def action_types(n: dict, attrs: dict[str,str]) -> list[str]:
    tag = node_tag(n)
    typ = attrs.get("type", "").lower()
    role = attrs.get("role", "").lower()
    out = []
    if is_interactive(n, attrs):
        if tag in {"input", "textarea"} or role in {"textbox", "searchbox"}:
            out += ["focus", "type"]
        elif tag == "select" or role == "combobox":
            out += ["focus", "select"]
        elif tag == "input" and typ in {"checkbox", "radio"} or role in {"checkbox", "radio"}:
            out += ["toggle"]
        else:
            out += ["click"]
    if is_scrollable(n):
        out.append("scroll")
    return list(dict.fromkeys(out))


def simulate_structured(dom: dict) -> dict:
    nodes = dom.get("nodes") or []
    by_parent = defaultdict(list)
    by_id = {}
    for n in nodes:
        try: nid = int(n.get("nodeId"))
        except Exception: continue
        by_id[nid] = n
        try: by_parent[int(n.get("parentId"))].append(n)
        except Exception: pass
    dropped = Counter()
    candidates = []
    source_order = 0
    for n in nodes:
        source_order += 1
        tag = node_tag(n)
        attrs = attrs_map(n.get("attributes"))
        if tag in DECORATIVE:
            dropped["decorative_or_unsupported"] += 1
            continue
        if is_hidden(n, attrs):
            dropped["hidden_style_or_aria"] += 1
            continue
        dt = direct_text(n, by_parent)
        st = subtree_text(n, by_parent)
        has_text = bool(dt or st or node_text_save(n))
        if (not has_box(n)) and not has_text:
            dropped["no_box_and_no_text"] += 1
            continue
        role = attrs.get("role", "").lower()
        meaningful = tag in MEANINGFUL or role in BOUNDARY_ROLES
        candidate = meaningful or is_interactive(n, attrs) or is_scrollable(n) or has_text
        if not candidate:
            dropped["not_candidate"] += 1
            continue
        candidates.append((source_order, n, dt, st, attrs))
        if len(candidates) >= NODE_CAP:
            dropped["node_cap_break"] = max(0, len(nodes) - source_order)
            break
    out_nodes = []
    text_chars = 0
    for i, (source_order, n, dt, st, attrs) in enumerate(candidates, 1):
        if text_chars >= TEXT_BUDGET:
            dropped["text_budget_break"] = len(candidates) - len(out_nodes)
            break
        dt = dt[:TEXT_CAP_DIRECT]
        st = st[:TEXT_CAP_SUBTREE]
        add_chars = len(dt) + len(st)
        if text_chars + add_chars > TEXT_BUDGET:
            remain = max(0, TEXT_BUDGET - text_chars)
            if len(dt) > remain:
                dt = dt[:remain]
                st = ""
            else:
                st = st[:max(0, remain - len(dt))]
            add_chars = len(dt) + len(st)
        text_chars += add_chars
        attrs_sel = selected_attrs(attrs)
        rec = {
            "ref": f"n{i}",
            "nodeId": n.get("nodeId", i),
            "backendNodeId": n.get("backendNodeId", n.get("nodeId", i)),
            "parentNodeId": n.get("parentId"),
            "sourceOrder": source_order,
            "tag": node_tag(n),
            "role": attrs.get("role", ""),
            "directText": dt,
            "subtreeText": st,
            "selectedAttributes": attrs_sel,
            "states": node_states(n, attrs),
            "actionTypes": action_types(n, attrs),
            "bounds": bounds_box(n),
            "visible": bool(n.get("isVisible", True)),
            "inViewport": bool(n.get("isInViewport", False)),
            "hitTestable": n.get("isHitTestable"),
        }
        out_nodes.append(rec)
    return {
        "url": dom.get("url"),
        "title": dom.get("title"),
        "nodes": out_nodes,
        "stats": {
            "rawNodes": len(nodes),
            "returnedNodes": len(out_nodes),
            "textChars": text_chars,
            "nodeCap": NODE_CAP,
            "textBudget": TEXT_BUDGET,
            "truncatedByNodeCap": bool(dropped.get("node_cap_break")),
            "truncatedByTextBudget": bool(dropped.get("text_budget_break")),
            "dropped": dict(dropped),
        },
        "simulation": {
            "source": "reference/dom-refinement/chromium/inspector_chromiumrl_agent.cc",
            "notes": [
                "Runtime command unavailable; simulated from ChromiumRL.saveDOMState output.",
                "LayoutObject presence and exact hit testing cannot be reproduced from saveDOMState; bounds/isVisible/isInViewport/keyStyles were used.",
                "Computed accessible name and compositor occlusion are approximated/omitted because saveDOMState does not expose the same Blink internals.",
            ],
        },
    }


def normalize_save(dom: dict) -> list[dict]:
    out = []
    for n in dom.get("nodes") or []:
        attrs = attrs_map(n.get("attributes"))
        # The current stored saveDOMState artifact includes recorder-side form-property enrichment.
        # Include it for the saveDOMState method because the comparison is over the actual capture
        # artifacts available to a DOM-diff verifier. Do not use this in the structured snapshot
        # simulation; that command would only emit its own selectedAttributes/states.
        for k, v in (n.get("_semantic_attrs_override") or {}).items():
            attrs[k] = v
        ident = n.get("stablePath") or n.get("cssSelector") or n.get("xpath") or n.get("fingerprint") or n.get("nodeId")
        out.append({"id": str(ident), "tag": node_tag(n), "text": node_text_save(n), "attrs": attrs, "raw": n})
    return out


def obs_payload(obj: dict) -> dict:
    return (obj.get("result", {}) or {}).get("observation", obj.get("observation", obj)) or {}


def normalize_obs(obj: dict) -> list[dict]:
    ob = obs_payload(obj)
    out = []
    for e in ob.get("elements") or []:
        ident = e.get("selector") or e.get("fingerprint") or e.get("idx")
        attrs = {}
        for k in ("href", "value", "role", "text", "context"):
            if e.get(k) not in (None, ""):
                attrs[k] = str(e.get(k))
        text = norm_text(e.get("text") or e.get("accessibleName") or e.get("value") or e.get("context") or e.get("href") or "")
        out.append({"id": str(ident), "tag": str(e.get("tag") or ""), "text": text, "attrs": attrs, "raw": e})
    return out


def normalize_structured(ss: dict) -> list[dict]:
    out = []
    for n in ss.get("nodes") or []:
        ident = n.get("nodeId") or n.get("backendNodeId") or n.get("ref")
        attrs = {a.get("name"): a.get("value") for a in n.get("selectedAttributes") or [] if a.get("name")}
        for s in n.get("states") or []:
            attrs[f"state:{s.get('name')}"] = str(s.get("value"))
        text = norm_text((n.get("directText") or "") + " " + (n.get("subtreeText") or ""))
        out.append({"id": str(ident), "tag": n.get("tag") or "", "text": text, "attrs": attrs, "raw": n})
    return out


def make_map(nodes: list[dict]) -> dict[str, dict]:
    m = {}
    for n in nodes:
        if n["id"] and n["id"] not in m:
            m[n["id"]] = n
    return m


def diff_nodes(before: list[dict], after: list[dict]) -> dict:
    bm, am = make_map(before), make_map(after)
    common = sorted(set(bm) & set(am))
    added = [am[k] for k in sorted(set(am)-set(bm))]
    removed = [bm[k] for k in sorted(set(bm)-set(am))]
    changed = []
    for k in common:
        b, a = bm[k], am[k]
        kinds = []
        if b.get("text") != a.get("text"):
            kinds.append("text")
        keys = set((b.get("attrs") or {})) | set((a.get("attrs") or {}))
        for attr in sorted(keys):
            if (b.get("attrs") or {}).get(attr) != (a.get("attrs") or {}).get(attr):
                kinds.append(f"attr:{attr}")
        if kinds:
            changed.append({"id": k, "before": b, "after": a, "kind": kinds})
    return {"matched": len(common), "added": added, "removed": removed, "changed": changed}


def contains_in_node(n: dict, needle: str) -> bool:
    s = json.dumps(n, ensure_ascii=False).lower()
    return needle.lower() in s


def provable(diff: dict, needle: str, mode: str = "any") -> tuple[bool, str]:
    pool = []
    if mode in ("any", "after"):
        pool += diff["added"]
        pool += [c["after"] for c in diff["changed"]]
    if mode == "any":
        pool += diff["removed"]
        pool += [c["before"] for c in diff["changed"]]
    for n in pool:
        if contains_in_node(n, needle):
            return True, "present in added/changed diff evidence"
    return False, "not present in added/changed diff evidence"


def size_record(value: Any) -> dict:
    raw = len(compact_bytes(value))
    return {"raw_bytes": raw, "gzip_bytes": gz_size(value)}


def star_record_save(dom: dict) -> Any:
    for n in dom.get("nodes") or []:
        if "star-rating" in json.dumps(n.get("attributes") or [], ensure_ascii=False):
            return n
    return None


def star_record_obs(obj: dict) -> Any:
    for e in obs_payload(obj).get("elements") or []:
        if "star" in json.dumps(e, ensure_ascii=False).lower() or "rating" in json.dumps(e, ensure_ascii=False).lower():
            return e
    return None


def star_node_id_from_save(dom: dict) -> Any:
    rec = star_record_save(dom)
    return rec.get("nodeId") if isinstance(rec, dict) else None

def star_record_struct(ss: dict, node_id: Any = None) -> Any:
    if node_id is not None:
        for n in ss.get("nodes") or []:
            if n.get("nodeId") == node_id:
                return n
    return None


def coverage(method: str, value: Any) -> dict:
    if method == "saveDOMState":
        return {"captured": len(value.get("nodes") or []), "dropped": {}, "truncation": {"fired": False}}
    if method == "getAgentObservation":
        ob = obs_payload(value)
        st = ob.get("stats") or {}
        params = value.get("params") or {}
        returned = len(ob.get("elements") or [])
        cap = params.get("maxElements") or params.get("maxInteractiveElements")
        return {"captured": returned, "dropped": {k:v for k,v in st.items() if str(k).startswith("dropped")}, "stats": st, "truncation": {"fired": bool(cap and returned >= int(cap)), "cap": cap}, "dedup_examples": "UNAVAILABLE: dropped duplicate records are not emitted by getAgentObservation; only droppedDuplicate count is exposed."}
    ss = value
    return {"captured": len(ss.get("nodes") or []), "dropped": ss.get("stats",{}).get("dropped",{}), "truncation": {"node_cap": ss.get("stats",{}).get("truncatedByNodeCap"), "text_budget": ss.get("stats",{}).get("truncatedByTextBudget")}}


def report_json_block(obj: Any) -> str:
    return "```json\n" + json.dumps(obj, ensure_ascii=False, indent=2)[:12000] + "\n```"


def main():
    RAW_OUT.mkdir(parents=True, exist_ok=True)
    SIM_OUT.mkdir(parents=True, exist_ok=True)
    all_data = {}
    for task_dir in sorted(TASKS.glob("task-*")):
        task_data = {}
        for step_dir in sorted(task_dir.glob("step_*")):
            step_data = {}
            for phase in ("before", "after"):
                raw_path = step_dir / f"dom_{phase}_raw.json.gz"
                obs_path = step_dir / f"observation_{phase}.json.gz"
                if not raw_path.exists() or not obs_path.exists():
                    continue
                dom = load_json_gz(raw_path)
                obs = load_json_gz(obs_path)
                ss = simulate_structured(dom)
                sim_path = SIM_OUT / task_dir.name / step_dir.name / f"structured_{phase}.json.gz"
                write_json_gz(sim_path, ss)
                step_data[phase] = {"saveDOMState": dom, "getAgentObservation": obs, "captureStructuredSnapshot_sim": ss}
            if "before" in step_data and "after" in step_data:
                task_data[step_dir.name] = step_data
        all_data[task_dir.name] = task_data

    metrics = {"tasks": {}, "facts": {}, "star_records": {}, "simulation_unreproduced_filters": [
        "Exact LayoutObject availability; approximated from bounds plus text.",
        "Exact Blink accessible-name fallback order; approximated from raw text/selected attributes.",
        "Exact hit-test and compositor occlusion facts; saveDOMState does not expose them for all nodes.",
        "Closed shadow DOM and out-of-process frame internals are unavailable from saveDOMState.",
    ]}
    normalizers = {
        "saveDOMState": normalize_save,
        "getAgentObservation": normalize_obs,
        "captureStructuredSnapshot_sim": normalize_structured,
    }

    for task, steps in all_data.items():
        metrics["tasks"][task] = {}
        for step, sd in steps.items():
            metrics["tasks"][task][step] = {}
            for method in normalizers:
                before_obj = sd["before"][method]
                after_obj = sd["after"][method]
                before_nodes = normalizers[method](before_obj)
                after_nodes = normalizers[method](after_obj)
                d = diff_nodes(before_nodes, after_nodes)
                metrics["tasks"][task][step][method] = {
                    "matchability": {
                        "before": len(before_nodes),
                        "after": len(after_nodes),
                        "matched": d["matched"],
                        "match_rate_pct": round(100*d["matched"] / max(1, min(len(before_nodes), len(after_nodes))), 1),
                        "added": len(d["added"]),
                        "removed": len(d["removed"]),
                        "changed": len(d["changed"]),
                    },
                    "coverage_before": coverage(method, before_obj),
                    "coverage_after": coverage(method, after_obj),
                    "size_before": size_record(before_obj),
                    "size_after": size_record(after_obj),
                    "diff": d,
                }

    # Fact provability on decisive steps.
    fact_steps = {
        "Task A final book page": ("task-a-books-mystery", "step_003", {
            "book title": (FACTS["book_title"], "after"),
            "price": (FACTS["price"], "after"),
            "availability text": (FACTS["availability"], "after"),
            "star rating class": (FACTS["star_rating_actual"], "after"),
        }),
        "Task B username fill": ("task-b-quotes-login", "step_002", {"form field value": (FACTS["form_value"], "after")}),
        "Task B submit result": ("task-b-quotes-login", "step_004", {"post-submit page text": (FACTS["post_submit_text"], "after")}),
    }
    for label, (task, step, facts) in fact_steps.items():
        metrics["facts"][label] = {}
        for method in normalizers:
            d = metrics["tasks"][task][step][method]["diff"]
            metrics["facts"][label][method] = {}
            for fname, (needle, mode) in facts.items():
                ok, cause = provable(d, needle, mode)
                if not ok:
                    # cause refinement
                    after_obj = all_data[task][step]["after"][method]
                    if method == "captureStructuredSnapshot_sim" and fname == "star rating class":
                        cause = "attribute filtered out: class is intentionally absent from selectedAttributes"
                    elif method == "getAgentObservation" and fname == "star rating class":
                        cause = "hidden/non-interactive text/state not captured in interactive observation"
                    elif method == "captureStructuredSnapshot_sim" and fname == "form field value":
                        cause = "value property not mirrored into selectedAttributes by this lossy snapshot source"
                    elif contains_in_node(after_obj, needle):
                        cause = "present in capture but not provable from identity diff output"
                    else:
                        cause = "not captured by this representation"
                metrics["facts"][label][method][fname] = {"provable": ok, "cause": cause, "needle": needle}

    # star records after task A final page
    task, step = "task-a-books-mystery", "step_003"
    star_save = star_record_save(all_data[task][step]["after"]["saveDOMState"])
    star_node_id = star_save.get("nodeId") if isinstance(star_save, dict) else None
    metrics["star_records"] = {
        "saveDOMState": star_save,
        "getAgentObservation": star_record_obs(all_data[task][step]["after"]["getAgentObservation"]),
        "captureStructuredSnapshot_sim": star_record_struct(all_data[task][step]["after"]["captureStructuredSnapshot_sim"], star_node_id),
    }

    # compact output metrics without huge diff raw nodes
    public = json.loads(json.dumps(metrics, ensure_ascii=False, default=str))
    for task in public["tasks"].values():
        for step in task.values():
            for md in step.values():
                md.pop("diff", None)
    (OUT / "metrics_summary.json").write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")

    # write full star records
    (OUT / "star_rating_records.json").write_text(json.dumps(metrics["star_records"], ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append("# DOM Capture Method Comparison for DOM-DIFF Suitability\n")
    lines.append("This is a diagnostics-only measurement. No recorder or diff-builder source files were modified.\n")
    lines.append("## Method setup\n")
    lines.append("- `ChromiumRL.saveDOMState`: captured from the running browser via existing `--dom-capture full` artifacts (`dom_before_raw.json.gz` / `dom_after_raw.json.gz`).")
    lines.append("- `ChromiumRL.getAgentObservation`: captured from the running browser via `--keep-observations` artifacts.")
    lines.append("- `ChromiumRL.captureStructuredSnapshot`: unavailable in the running binary, so it was simulated from `saveDOMState` using the documented reference filters in `reference/dom-refinement/chromium/inspector_chromiumrl_agent.cc`. Simulated raw outputs are in `diagnostics/dom-capture-comparison/structured_simulated/`.\n")
    lines.append("### Structured-snapshot simulation fidelity\n")
    lines.append("Implemented filters: decorative/unsupported node dropping; hidden/style/aria-hidden dropping; no-box-and-no-text dropping; structured candidate filtering; hard 700-node traversal-order cap; 24,000-character text budget; 240/500 direct/subtree text caps; selected-attribute allow-list without `class` or `id`; no computed-style fields; identity limited to `nodeId`/`backendNodeId`/`ref`.\n")
    lines.append("Filters/facts that could not be exactly reproduced from `saveDOMState`: " + "; ".join(metrics["simulation_unreproduced_filters"]) + ".\n")

    lines.append("## Matchability\n")
    for task, steps in public["tasks"].items():
        lines.append(f"### {task}\n")
        lines.append("| step | method | before | after | matched | match rate | added | removed | changed |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for step, methods in steps.items():
            for method, md in methods.items():
                m = md["matchability"]
                lines.append(f"| {step} | {method} | {m['before']} | {m['after']} | {m['matched']} | {m['match_rate_pct']}% | {m['added']} | {m['removed']} | {m['changed']} |")
        lines.append("")
    lines.append("Cross-document interpretation: `captureStructuredSnapshot_sim` had 0 matched nodes on the observed cross-document steps. That confirms the expected failure mode: nodeId/ref identity is per-document and provides no structural path key for navigation diffs.\n")

    lines.append("## Provability\n")
    for label, methods in metrics["facts"].items():
        lines.append(f"### {label}\n")
        lines.append("| fact | saveDOMState | getAgentObservation | captureStructuredSnapshot simulated |")
        lines.append("|---|---|---|---|")
        fact_names = next(iter(methods.values())).keys()
        for fact in fact_names:
            row = [fact]
            for method in ("saveDOMState", "getAgentObservation", "captureStructuredSnapshot_sim"):
                r = methods[method][fact]
                row.append(("provable" if r["provable"] else "not provable") + f" — {r['cause']}")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    lines.append("Note: the actual second Mystery book in this run was `In a Dark, Dark Wood`, whose rating class is `star-rating One`. The user-provided `star-rating Three` example is still the discriminating property: the rating is class-only, and structured snapshot selected attributes intentionally exclude `class`.\n")

    lines.append("## Coverage and truncation\n")
    for task, steps in public["tasks"].items():
        lines.append(f"### {task}\n")
        lines.append("| step | method | before captured | after captured | before dropped/truncation | after dropped/truncation |")
        lines.append("|---|---:|---:|---:|---|---|")
        for step, methods in steps.items():
            for method, md in methods.items():
                cb, ca = md["coverage_before"], md["coverage_after"]
                lines.append(f"| {step} | {method} | {cb.get('captured')} | {ca.get('captured')} | dropped={cb.get('dropped',{})}, trunc={cb.get('truncation',{})} | dropped={ca.get('dropped',{})}, trunc={ca.get('truncation',{})} |")
        lines.append("")
    lines.append("For `getAgentObservation`, `droppedDuplicate` is reported by the browser stats, but the payload does not include the dropped elements. Exact names of deduplicated examples are therefore unavailable from the artifact. Non-zero counts occurred on Task A step_002 after (`droppedDuplicate=1`) and Task B step_004 after (`droppedDuplicate=8`); likely repeated-label pressure on these pages includes repeated author/about links and repeated category/navigation labels, but the exact dropped records are not emitted and cannot be named faithfully.\n")

    lines.append("## Size\n")
    for task, steps in public["tasks"].items():
        lines.append(f"### {task}\n")
        lines.append("| step | method | before raw bytes | before gzip bytes | after raw bytes | after gzip bytes |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for step, methods in steps.items():
            for method, md in methods.items():
                sb, sa = md["size_before"], md["size_after"]
                lines.append(f"| {step} | {method} | {sb['raw_bytes']} | {sb['gzip_bytes']} | {sa['raw_bytes']} | {sa['gzip_bytes']} |")
        lines.append("")

    lines.append("## Star-rating element records\n")
    lines.append("### saveDOMState\n" + report_json_block(metrics["star_records"]["saveDOMState"]))
    lines.append("### getAgentObservation\n" + report_json_block(metrics["star_records"]["getAgentObservation"]))
    lines.append("### captureStructuredSnapshot simulated\n" + report_json_block(metrics["star_records"]["captureStructuredSnapshot_sim"]))

    lines.append("## Verdict\n")
    lines.append("1. **Best: `ChromiumRL.saveDOMState`** for DOM-diff evidence. It captures the full DOM node set, structural identity keys, attributes including `class`, and enough non-interactive text to prove title/price/availability/rating/form-result facts. The star rating is provable only here because the evidence is `class=\"star-rating One\"`.")
    lines.append("2. **Middle: `ChromiumRL.getAgentObservation`**. It is small and action-oriented, but it is capped/interactive-focused and drops non-interactive DOM state. It could prove some visible text and form values, but not class-only star rating evidence in this task.")
    lines.append("3. **Worst: `captureStructuredSnapshot` simulated from the reference design** for verifier DOM diff. It is useful as model observation, but unsuitable as primary DOM-diff evidence because it intentionally removes `class`/`id`, has no structural path identity, and is capped at 700 traversal-order nodes / 24k text chars. The single decisive number here: on Task A step_003 it captured the product page in " + str(public['tasks']['task-a-books-mystery']['step_003']['captureStructuredSnapshot_sim']['matchability']['after']) + " nodes but still could not prove the class-only star rating because `class` is not in `selectedAttributes`. That is a data-loss problem, not a differ problem.\n")
    lines.append("Plain-language bottom line: **structured snapshot is a good agent-observation candidate, but the worst DOM-diff evidence source, because it deliberately drops exactly the kind of semantic DOM attribute (`class`) needed to prove common UI state such as ratings, selected tabs, and active statuses.**\n")

    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT / "REPORT.md")
    print("wrote", OUT / "metrics_summary.json")
    print("wrote", OUT / "star_rating_records.json")
    print("wrote simulated snapshots under", SIM_OUT)

if __name__ == "__main__":
    main()
