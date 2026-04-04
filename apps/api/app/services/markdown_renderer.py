"""
services/markdown_renderer.py — Deterministic PRD → Markdown renderer.

Public API
----------
    render_prd_markdown(prd: dict) -> str

Design contract
---------------
- Pure function: dict in, str out.  No I/O, no side-effects, no global state.
- Deterministic: identical input always produces identical output.
- Fault-tolerant: never raises; missing / None sections are skipped or shown
  as "[미입력]" placeholder so partial PRDs (Turn 1–4) render cleanly.
- Section order is fixed (matches PRD_SCHEMA.json required order).
- Output format: standard GitHub Flavored Markdown (GFM).
  Tables use GFM pipe syntax; fenced code blocks use triple-backtick.
- Bilingual headings: metadata.language == "en-US" → English section labels;
  everything else (including "ko-KR" or absent) → Korean labels (default).

Scope guard
-----------
- No LLM calls.
- No file I/O.
- Validation execution / packaging: T05.
- MiroFish integration: T10.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Heading translations
# ---------------------------------------------------------------------------
_HEADINGS_KO: dict[str, str] = {
    "doc_title":        "{name} — PRD v{version}",
    "metadata":         "메타데이터 (Metadata)",
    "product":          "제품 개요 (Product)",
    "users":            "사용자 (Users)",
    "problem":          "문제 정의 (Problem)",
    "solution":         "솔루션 (Solution)",
    "scope":            "범위 (Scope)",
    "requirements":     "요구사항 (Requirements)",
    "success_metrics":  "성공 지표 (Success Metrics)",
    "delivery":         "딜리버리 (Delivery)",
    "assumptions":      "가정사항 (Assumptions)",
    "risks":            "리스크 (Risks)",
    "open_questions":   "미결 사항 (Open Questions)",
    "validation":       "검증 계획 (Validation)",
    # sub-labels
    "primary_personas": "주요 페르소나",
    "secondary_personas": "보조 페르소나",
    "non_targets":      "대상 외 사용자",
    "pain_points":      "페인포인트",
    "goals":            "목표",
    "key_features":     "핵심 기능",
    "user_journey":     "사용자 여정",
    "mvp_in_scope":     "MVP 포함 범위",
    "out_of_scope":     "MVP 제외 범위",
    "future_expansion": "향후 확장",
    "launch_constraints": "출시 제약",
    "functional":       "기능 요구사항 (FR)",
    "non_functional":   "비기능 요구사항 (NFR)",
    "acceptance_criteria": "인수 기준",
    "integrations":     "외부 연동",
    "product_metrics":  "제품 지표",
    "guardrail_metrics":"가드레일 지표",
    "dependencies":     "의존성",
    "team_assumptions": "팀 가정",
    "validation_templates": "검증 템플릿",
    "must_answer_questions": "필수 답변 질문",
    "empty_placeholder": "[미입력]",
}

_HEADINGS_EN: dict[str, str] = {
    "doc_title":        "{name} — PRD v{version}",
    "metadata":         "Metadata",
    "product":          "Product Overview",
    "users":            "Users",
    "problem":          "Problem Definition",
    "solution":         "Solution",
    "scope":            "Scope",
    "requirements":     "Requirements",
    "success_metrics":  "Success Metrics",
    "delivery":         "Delivery",
    "assumptions":      "Assumptions",
    "risks":            "Risks",
    "open_questions":   "Open Questions",
    "validation":       "Validation Plan",
    # sub-labels
    "primary_personas": "Primary Personas",
    "secondary_personas": "Secondary Personas",
    "non_targets":      "Non-Targets",
    "pain_points":      "Pain Points",
    "goals":            "Goals",
    "key_features":     "Key Features",
    "user_journey":     "User Journey",
    "mvp_in_scope":     "MVP In Scope",
    "out_of_scope":     "Out of Scope",
    "future_expansion": "Future Expansion",
    "launch_constraints": "Launch Constraints",
    "functional":       "Functional Requirements (FR)",
    "non_functional":   "Non-Functional Requirements (NFR)",
    "acceptance_criteria": "Acceptance Criteria",
    "integrations":     "Integrations",
    "product_metrics":  "Product Metrics",
    "guardrail_metrics":"Guardrail Metrics",
    "dependencies":     "Dependencies",
    "team_assumptions": "Team Assumptions",
    "validation_templates": "Validation Templates",
    "must_answer_questions": "Must-Answer Questions",
    "empty_placeholder": "[Not Filled]",
}


def _get_headings(language: str | None) -> dict[str, str]:
    """Return the correct heading dict based on language code."""
    if language == "en-US":
        return _HEADINGS_EN
    return _HEADINGS_KO  # default (ko-KR, None, unknown)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _safe(value: Any, fallback: str = "") -> str:
    """Return string representation of value, or fallback if None/empty.

    Enum objects (e.g. PrdStatus.DRAFTING) are serialised using .value so
    the renderer produces the same output whether the dict was built from
    an in-process model_dump() or round-tripped through JSON (where enums
    are already strings).
    """
    if value is None:
        return fallback
    # Unwrap enum .value if present (handles both str-enum and int-enum)
    raw = getattr(value, "value", value)
    s = str(raw)
    return s if s.strip() else fallback


def _bullet_list(items: list[Any] | None) -> str:
    """Convert a list to a Markdown bullet list string.  Returns '' if empty."""
    if not items:
        return ""
    lines = [f"- {_safe(item)}" for item in items if item is not None]
    return "\n".join(lines)


def _gfm_table(headers: list[str], rows: list[list[str]]) -> str:
    """
    Build a GFM pipe table from headers and rows.

    All cell values are already strings; internal pipe characters are escaped.
    Returns '' if rows is empty.
    """
    if not rows:
        return ""

    def _escape(cell: str) -> str:
        return cell.replace("|", "\\|").replace("\n", " ")

    header_row = "| " + " | ".join(_escape(h) for h in headers) + " |"
    separator  = "| " + " | ".join("---" for _ in headers) + " |"
    data_rows  = [
        "| " + " | ".join(_escape(str(c)) for c in row) + " |"
        for row in rows
    ]
    return "\n".join([header_row, separator] + data_rows)


# ---------------------------------------------------------------------------
# Section renderers — each returns a str block (may be empty str)
# ---------------------------------------------------------------------------

def _render_title(prd: dict, h: dict) -> str:
    product   = prd.get("product") or {}
    metadata  = prd.get("metadata") or {}
    name      = _safe(product.get("name"), "Untitled PRD")
    version   = _safe(metadata.get("version"), "0.1.0")
    title     = h["doc_title"].format(name=name, version=version)
    schema_v  = _safe(prd.get("schema_version"), "0.1.0")
    return f"# {title}\n\n> schema_version: `{schema_v}`"


def _render_metadata(prd: dict, h: dict) -> str:
    m = prd.get("metadata")
    if not m:
        return ""
    lines = [f"## {h['metadata']}", ""]
    fields = [
        ("Project ID", m.get("project_id")),
        ("Status",     m.get("status")),
        ("Language",   m.get("language")),
        ("Owner",      m.get("owner")),
        ("Version",    m.get("version")),
        ("Created",    m.get("created_at")),
        ("Updated",    m.get("updated_at")),
    ]
    for label, val in fields:
        if val is not None:
            lines.append(f"- **{label}**: {_safe(val)}")
    # Source sub-object
    source = m.get("source")
    if source:
        mode = _safe(source.get("mode"))
        turn = source.get("chat_turn_count")
        sid  = source.get("session_id")
        src_parts = [f"mode={mode}"]
        if turn is not None:
            src_parts.append(f"turns={turn}")
        if sid:
            src_parts.append(f"session={sid}")
        lines.append(f"- **Source**: {', '.join(src_parts)}")
    return "\n".join(lines)


def _render_product(prd: dict, h: dict) -> str:
    p = prd.get("product")
    if not p:
        return ""
    lines = [f"## {h['product']}", ""]
    pairs = [
        ("Name",             p.get("name")),
        ("One-liner",        p.get("one_liner")),
        ("Category",         p.get("category")),
        ("Stage",            p.get("stage")),
        ("Domain Context",   p.get("domain_context")),
    ]
    for label, val in pairs:
        if val is not None:
            lines.append(f"- **{label}**: {_safe(val)}")
    # platforms list
    platforms = p.get("platforms")
    if platforms:
        lines.append(f"- **Platforms**: {', '.join(_safe(x) for x in platforms)}")
    # industry_context list
    industry = p.get("industry_context")
    if industry:
        lines.append(f"- **Industry Context**: {', '.join(_safe(x) for x in industry)}")
    return "\n".join(lines)


def _render_persona_block(persona: dict, h: dict) -> str:
    """Render a single Persona as a sub-block."""
    name = _safe(persona.get("name"), "?")
    role = _safe(persona.get("role"), "")
    lines = [f"#### {name} ({role})"]
    company = persona.get("company_type")
    context = persona.get("context")
    if company:
        lines.append(f"- **Company type**: {company}")
    if context:
        lines.append(f"- **Context**: {context}")
    goals = persona.get("goals")
    if goals:
        lines.append(f"\n**{h['goals']}**")
        lines.append(_bullet_list(goals))
    pain_points = persona.get("pain_points")
    if pain_points:
        lines.append(f"\n**{h['pain_points']}**")
        lines.append(_bullet_list(pain_points))
    return "\n".join(lines)


def _render_users(prd: dict, h: dict) -> str:
    u = prd.get("users")
    if not u:
        return ""
    lines = [f"## {h['users']}", ""]

    primary = u.get("primary_personas") or []
    if primary:
        lines.append(f"### {h['primary_personas']}")
        lines.append("")
        for p in primary:
            lines.append(_render_persona_block(p, h))
            lines.append("")

    secondary = u.get("secondary_personas") or []
    if secondary:
        lines.append(f"### {h['secondary_personas']}")
        lines.append("")
        for p in secondary:
            lines.append(_render_persona_block(p, h))
            lines.append("")

    non_targets = u.get("non_targets")
    if non_targets:
        lines.append(f"### {h['non_targets']}")
        lines.append("")
        lines.append(_bullet_list(non_targets))

    return "\n".join(lines)


def _render_problem(prd: dict, h: dict) -> str:
    prob = prd.get("problem")
    if not prob:
        return ""
    lines = [f"## {h['problem']}", ""]
    core = prob.get("core_problem")
    if core:
        lines.append(f"**Core Problem**: {_safe(core)}")
        lines.append("")
    pain_points = prob.get("pain_points")
    if pain_points:
        lines.append(f"**{h['pain_points']}**")
        lines.append(_bullet_list(pain_points))
        lines.append("")
    alternatives = prob.get("current_alternatives")
    if alternatives:
        lines.append("**Current Alternatives**")
        lines.append(_bullet_list(alternatives))
        lines.append("")
    why_now = prob.get("why_now")
    if why_now:
        lines.append(f"**Why Now**: {_safe(why_now)}")
        lines.append("")
    jtbd = prob.get("jobs_to_be_done")
    if jtbd:
        lines.append("**Jobs To Be Done**")
        lines.append(_bullet_list(jtbd))
    return "\n".join(lines).rstrip()


def _render_solution(prd: dict, h: dict) -> str:
    sol = prd.get("solution")
    if not sol:
        return ""
    lines = [f"## {h['solution']}", ""]

    summary = sol.get("summary")
    if summary:
        lines.append(f"**Summary**: {_safe(summary)}")
        lines.append("")
    value_prop = sol.get("value_proposition")
    if value_prop:
        lines.append(f"**Value Proposition**: {_safe(value_prop)}")
        lines.append("")

    # key_features → GFM table
    features = sol.get("key_features") or []
    if features:
        lines.append(f"### {h['key_features']}")
        lines.append("")
        rows = [
            [
                _safe(f.get("name")),
                _safe(f.get("description")),
                _safe(f.get("priority")),
                _safe(f.get("rationale")),
            ]
            for f in features
        ]
        lines.append(_gfm_table(["기능명", "설명", "우선순위", "근거"], rows))
        lines.append("")

    user_journey = sol.get("user_journey")
    if user_journey:
        lines.append(f"### {h['user_journey']}")
        lines.append("")
        for i, step in enumerate(user_journey, 1):
            lines.append(f"{i}. {_safe(step)}")

    return "\n".join(lines).rstrip()


def _render_scope(prd: dict, h: dict) -> str:
    sc = prd.get("scope")
    if not sc:
        return ""
    lines = [f"## {h['scope']}", ""]

    mvp_in = sc.get("mvp_in_scope")
    if mvp_in:
        lines.append(f"### ✅ {h['mvp_in_scope']}")
        lines.append("")
        lines.append(_bullet_list(mvp_in))
        lines.append("")

    out_of = sc.get("out_of_scope")
    if out_of:
        lines.append(f"### ❌ {h['out_of_scope']}")
        lines.append("")
        lines.append(_bullet_list(out_of))
        lines.append("")

    future = sc.get("future_expansion")
    if future:
        lines.append(f"### 🔮 {h['future_expansion']}")
        lines.append("")
        lines.append(_bullet_list(future))
        lines.append("")

    constraints = sc.get("launch_constraints")
    if constraints:
        lines.append(f"### ⚠️ {h['launch_constraints']}")
        lines.append("")
        lines.append(_bullet_list(constraints))

    return "\n".join(lines).rstrip()


def _render_requirements(prd: dict, h: dict) -> str:
    req = prd.get("requirements")
    if not req:
        return ""
    lines = [f"## {h['requirements']}", ""]

    def _req_table(items: list[dict]) -> str:
        rows = [
            [
                _safe(r.get("id")),
                _safe(r.get("statement")),
                _safe(r.get("priority")),
                _safe(r.get("notes")),
            ]
            for r in items
        ]
        return _gfm_table(["ID", "내용", "우선순위", "비고"], rows)

    functional = req.get("functional") or []
    if functional:
        lines.append(f"### {h['functional']}")
        lines.append("")
        lines.append(_req_table(functional))
        lines.append("")

    non_functional = req.get("non_functional") or []
    if non_functional:
        lines.append(f"### {h['non_functional']}")
        lines.append("")
        lines.append(_req_table(non_functional))
        lines.append("")

    acceptance = req.get("acceptance_criteria")
    if acceptance:
        lines.append(f"### {h['acceptance_criteria']}")
        lines.append("")
        lines.append(_bullet_list(acceptance))
        lines.append("")

    integrations = req.get("integrations") or []
    if integrations:
        lines.append(f"### {h['integrations']}")
        lines.append("")
        rows = [
            [_safe(i.get("name")), _safe(i.get("type")), _safe(i.get("purpose"))]
            for i in integrations
        ]
        lines.append(_gfm_table(["이름", "유형", "목적"], rows))

    return "\n".join(lines).rstrip()


def _render_success_metrics(prd: dict, h: dict) -> str:
    sm = prd.get("success_metrics")
    if not sm:
        return ""
    lines = [f"## {h['success_metrics']}", ""]

    north_star = sm.get("north_star")
    if north_star:
        lines.append(f"**North Star Metric**: {_safe(north_star)}")
        lines.append("")

    def _metric_table(metrics: list[dict]) -> str:
        rows = [
            [
                _safe(m.get("name")),
                _safe(m.get("target")),
                _safe(m.get("timeframe")),
                _safe(m.get("notes")),
            ]
            for m in metrics
        ]
        return _gfm_table(["지표명", "목표값", "기간", "비고"], rows)

    product_metrics = sm.get("product_metrics") or []
    if product_metrics:
        lines.append(f"### {h['product_metrics']}")
        lines.append("")
        lines.append(_metric_table(product_metrics))
        lines.append("")

    guardrail_metrics = sm.get("guardrail_metrics") or []
    if guardrail_metrics:
        lines.append(f"### {h['guardrail_metrics']}")
        lines.append("")
        lines.append(_metric_table(guardrail_metrics))

    return "\n".join(lines).rstrip()


def _render_delivery(prd: dict, h: dict) -> str:
    d = prd.get("delivery")
    if not d:
        return ""
    lines = [f"## {h['delivery']}", ""]

    pairs = [
        ("Priority",              d.get("priority")),
        ("Timeline Confidence",   d.get("timeline_confidence")),
        ("Target Release",        d.get("target_release")),
    ]
    for label, val in pairs:
        if val is not None:
            lines.append(f"- **{label}**: {_safe(val)}")

    dependencies = d.get("dependencies")
    if dependencies:
        lines.append(f"\n**{h['dependencies']}**")
        lines.append(_bullet_list(dependencies))

    team_assumptions = d.get("team_assumptions")
    if team_assumptions:
        lines.append(f"\n**{h['team_assumptions']}**")
        lines.append(_bullet_list(team_assumptions))

    return "\n".join(lines).rstrip()


def _render_assumptions(prd: dict, h: dict) -> str:
    items = prd.get("assumptions")
    if not items:
        return ""
    lines = [f"## {h['assumptions']}", ""]
    rows = [
        [
            _safe(item.get("text")),
            _safe(item.get("tag")),
            _safe(item.get("severity")),
        ]
        for item in items
    ]
    lines.append(_gfm_table(["내용", "태그", "심각도"], rows))
    return "\n".join(lines)


def _render_risks(prd: dict, h: dict) -> str:
    items = prd.get("risks")
    if not items:
        return ""
    lines = [f"## {h['risks']}", ""]
    rows = [
        [
            _safe(r.get("title")),
            _safe(r.get("description")),
            _safe(r.get("severity")),
            _safe(r.get("mitigation")),
            _safe(r.get("owner")),
        ]
        for r in items
    ]
    lines.append(_gfm_table(["제목", "설명", "심각도", "완화책", "담당자"], rows))
    return "\n".join(lines)


def _render_open_questions(prd: dict, h: dict) -> str:
    items = prd.get("open_questions")
    if not items:
        return ""
    lines = [f"## {h['open_questions']}", ""]
    rows = [
        [
            _safe(item.get("text")),
            _safe(item.get("tag")),
            _safe(item.get("severity")),
        ]
        for item in items
    ]
    lines.append(_gfm_table(["질문", "태그", "심각도"], rows))
    return "\n".join(lines)


def _render_validation(prd: dict, h: dict) -> str:
    val = prd.get("validation")
    if not val:
        return ""
    lines = [f"## {h['validation']}", ""]

    goals = val.get("goals")
    if goals:
        lines.append(f"**{h['goals']}**")
        lines.append(_bullet_list(goals))
        lines.append("")

    sim_req = val.get("simulation_requirement")
    if sim_req:
        lines.append(f"**Simulation Requirement**: {_safe(sim_req)}")
        lines.append("")

    # Stakeholders → table
    stakeholders = val.get("stakeholder_personas") or []
    if stakeholders:
        lines.append("**Stakeholders**")
        lines.append("")
        rows = []
        for s in stakeholders:
            objections = s.get("likely_objections") or []
            objections_str = "; ".join(_safe(o) for o in objections) if objections else ""
            rows.append([
                _safe(s.get("name")),
                _safe(s.get("role")),
                _safe(s.get("review_angle")),
                objections_str,
            ])
        lines.append(_gfm_table(
            ["이름", "역할", "검토 각도", "예상 반론"],
            rows,
        ))
        lines.append("")

    templates = val.get("validation_templates")
    if templates:
        lines.append(f"**{h['validation_templates']}**: {', '.join(_safe(t) for t in templates)}")
        lines.append("")

    must_answer = val.get("must_answer_questions")
    if must_answer:
        lines.append(f"**{h['must_answer_questions']}**")
        lines.append(_bullet_list(must_answer))

    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Section pipeline — ordered list of (section_key, renderer_fn)
# The title renderer is special (always first, uses composite data).
# ---------------------------------------------------------------------------
_SECTION_RENDERERS: list[tuple[str | None, Any]] = [
    (None,               _render_title),         # synthetic — uses product + metadata
    ("metadata",         _render_metadata),
    ("product",          _render_product),
    ("users",            _render_users),
    ("problem",          _render_problem),
    ("solution",         _render_solution),
    ("scope",            _render_scope),
    ("requirements",     _render_requirements),
    ("success_metrics",  _render_success_metrics),
    ("delivery",         _render_delivery),
    ("assumptions",      _render_assumptions),
    ("risks",            _render_risks),
    ("open_questions",   _render_open_questions),
    ("validation",       _render_validation),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_prd_markdown(prd: dict[str, Any] | None) -> str:
    """
    Render a PRD dict (PRDDocument.model_dump() output) as a Markdown string.

    Parameters
    ----------
    prd : dict | None
        A dict produced by PRDDocument.model_dump(), or a partial dict
        produced during an in-progress chat session, or None / {}.

    Returns
    -------
    str
        A UTF-8 Markdown string.  Never raises; empty / None input returns
        a minimal placeholder document.
    """
    if not prd:
        return "# PRD\n\n> [미입력] No PRD data available yet.\n"

    # Determine language for heading selection
    metadata = prd.get("metadata") or {}
    language = metadata.get("language")
    h = _get_headings(language)

    blocks: list[str] = []
    for _section_key, renderer_fn in _SECTION_RENDERERS:
        try:
            block = renderer_fn(prd, h)
        except Exception:  # pragma: no cover — defensive; should never fire
            block = ""
        if block and block.strip():
            blocks.append(block)

    if not blocks:
        return "# PRD\n\n> [미입력] No PRD data available yet.\n"

    return "\n\n".join(blocks) + "\n"
