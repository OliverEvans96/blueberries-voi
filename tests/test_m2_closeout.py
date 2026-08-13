"""T-034 M2 close-out — RED / Definition-of-Done contract checks.

Asserts M2 plan §5 / `.team/specs/T-034.md` process artifacts and non-goals.
Does not implement product features; fails until close-out documentation lands.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

import pytest

import blueberries_voi.filter as filter_pkg

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEAM = _REPO_ROOT / ".team"
_SPECS = _TEAM / "specs"
_QA = _TEAM / "qa"
_REVIEWS = _TEAM / "reviews"
_CHANGELOG = _TEAM / "changelog.md"
_BACKLOG = _TEAM / "backlog.md"
_PLAN = _TEAM / "plans" / "M2-controller.md"
_SRC = _REPO_ROOT / "src" / "blueberries_voi"
_CONTROLLER = _SRC / "controller"
_VOI = _SRC / "voi"

# Implementation tickets that must be closed for M2 DoD (T-034 AC).
_M2_TICKETS: tuple[str, ...] = tuple(f"T-{n:03d}" for n in range(23, 34))

_LOCKED_RUNTIME_DEPS = frozenset({"numpy", "scipy"})  # ADR 0101 / T-046 slim core
_FORBIDDEN_CONTROLLER_IMPORTS = frozenset(
    {"matplotlib", "pyplot", "pyarrow", "PIL", "plotly"}
)

_PASS_STATUS = re.compile(
    r"^STATUS:\s*(?:PASS|GREEN|APPROVED)\b",
    re.IGNORECASE | re.MULTILINE,
)
_RED_STATUS = re.compile(
    r"^STATUS:\s*(?:RED|FAIL|CHANGES[_\s-]?REQUESTED)\b",
    re.IGNORECASE | re.MULTILINE,
)
_APPROVED = re.compile(r"^STATUS:\s*APPROVED\b", re.IGNORECASE | re.MULTILINE)

# Positive ship-claim detectors (allow-listed when negated nearby).
_BROWSER_SHIP_CLAIM = re.compile(
    r"(?:(?:ship(?:ped|ping)?|landed|deployed|released|packag(?:e|ed|ing)|"
    r"wasm|wheel)\b.{0,60}\b(?:pyodide|eng-?01|browser\s+demo|wasm)\b|"
    r"\b(?:pyodide|eng-?01|browser\s+demo|wasm)\b.{0,60}\b"
    r"(?:ship(?:ped|ping)?|landed|deployed|released|packag(?:e|ed|ing)|"
    r"complete|done|delivered)\b)",
    re.IGNORECASE | re.DOTALL,
)
_VOI_DOLLAR_HEADLINE = re.compile(
    r"(?:\$\s*\d|dollar\s+voi|voi\s+dollar|voi\s+sweep\s+(?:shipped|complete|done)|"
    r"value.of.information\s+(?:table|grid|sweep)\s+(?:shipped|complete))",
    re.IGNORECASE,
)


def _read(path: Path) -> str:
    assert path.is_file(), f"missing required artifact: {path}"
    return path.read_text(encoding="utf-8")


def _section(md: str, heading: str) -> str:
    """Return body under ``## heading`` until the next ``## `` heading."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(md)
    assert match is not None, f"missing '## {heading}' section"
    rest = md[match.end() :]
    next_h = re.search(r"^##\s+", rest, re.MULTILINE)
    return rest if next_h is None else rest[: next_h.start()]


def _ac_checkboxes(spec_text: str) -> list[tuple[bool, str]]:
    """Parse acceptance-criteria checkboxes (not Open questions)."""
    body = _section(spec_text, "Acceptance criteria")
    items: list[tuple[bool, str]] = []
    for line in body.splitlines():
        m = re.match(r"^\s*-\s*\[([ xX])\]\s*(.+)$", line)
        if m:
            items.append((m.group(1).lower() == "x", m.group(2).strip()))
    return items


def _primary_qa(ticket: str) -> Path | None:
    primary = _QA / f"{ticket}.md"
    return primary if primary.is_file() else None


def _review_paths_covering(ticket: str) -> list[Path]:
    """Reviews whose subject is this ticket (filename tokens or M2 close-out)."""
    found: list[Path] = []
    if not _REVIEWS.is_dir():
        return found
    for path in sorted(_REVIEWS.glob("*.md")):
        if path.name == "README.md":
            continue
        stem_tokens = re.findall(r"T-\d{3}", path.stem.upper())
        if ticket in stem_tokens:
            found.append(path)
            continue
        stem_u = path.stem.upper().replace("_", "-")
        if stem_u not in {"M2", "T-034", "M2-CLOSEOUT", "M2-DOD"}:
            continue
        text = path.read_text(encoding="utf-8")
        covers = bool(
            re.search(rf"\b{re.escape(ticket)}\b", text)
            or re.search(r"T-023\s*[\u2013\u2014\-]\s*T-033", text)
            or re.search(r"T-023\s+through\s+T-033", text, re.I)
            or re.search(r"all of T-023", text, re.I)
        )
        if covers:
            found.append(path)
    return list(dict.fromkeys(found))


def _closeout_dod_candidates() -> list[Path]:
    """Signed plan §5 DoD checklist copies (reviews / team close-out notes).

    Excludes M1.5 close-out notes that also contain DoD checklists.
    """
    names = (
        "M2.md",
        "M2-closeout.md",
        "M2-dod.md",
        "T-034.md",
        "m2-closeout.md",
    )
    out: list[Path] = []
    for name in names:
        for base in (_REVIEWS, _TEAM):
            p = base / name
            if p.is_file():
                out.append(p)
    if _REVIEWS.is_dir():
        for p in sorted(_REVIEWS.glob("*.md")):
            if p in out or p.name == "README.md":
                continue
            stem_u = p.stem.upper().replace("_", "-")
            if stem_u.startswith("M1.5") or stem_u.startswith("M15"):
                continue
            text = p.read_text(encoding="utf-8")
            if not re.search(r"\bM2\b", text):
                continue
            if re.search(r"-\s*\[[xX ]\]", text) and re.search(
                r"definition of done|DoD checklist|plan §5|plan § 5|M2 close-out",
                text,
                re.I,
            ):
                out.append(p)
    return list(dict.fromkeys(out))


def _changelog_m2_closeout_entry() -> str | None:
    """Return the changelog block that looks like the M2 close-out summary."""
    if not _CHANGELOG.is_file():
        return None
    text = _CHANGELOG.read_text(encoding="utf-8")
    # Prefer an explicit M2 close-out / controller+multi-scenario summary heading.
    heading = re.search(
        r"^##\s+.*\bM2\b.*(?:close-?out|complete|"
        r"controller.{0,40}multi[- ]scenario).*$",
        text,
        re.I | re.M,
    )
    if heading is None:
        heading = re.search(
            r"^##\s+.*(?:controller and multi-scenario|M2 —|M2 -).*$",
            text,
            re.I | re.M,
        )
    if heading is not None:
        rest = text[heading.start() :]
        nxt = re.search(r"^##\s+", rest[3:], re.M)
        return rest if nxt is None else rest[: nxt.start() + 3]
    return None


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".", maxsplit=1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", maxsplit=1)[0])
    return imported


def _negated_claim_window(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 48) : end + 16]
    return bool(
        re.search(
            r"\b(?:no|not|without|non-goal|never|exclude|parked|out of scope|"
            r"do not|don't|asserts?\s+no)\b",
            window,
            re.I,
        )
    )


# ---------------------------------------------------------------------------
# AC: .team/qa/ PASS for T-023-T-033
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticket", _M2_TICKETS)
def test_m2_ticket_qa_record_green(ticket: str) -> None:
    """Primary QA record exists and STATUS is PASS/GREEN (not open RED)."""
    path = _primary_qa(ticket)
    assert path is not None, (
        f"missing .team/qa/{ticket}.md — M2 close-out requires a green QA record"
    )
    text = _read(path)
    if _RED_STATUS.search(text):
        needs_human = bool(
            re.search(r"needs-human", text, re.I)
            or (
                _BACKLOG.is_file()
                and re.search(
                    rf"{ticket}.*needs-human|needs-human.*{ticket}",
                    _BACKLOG.read_text(encoding="utf-8"),
                    re.I | re.S,
                )
            )
        )
        assert needs_human, (
            f"{path} is RED/FAIL without needs-human escalation "
            f"(T-034: no open red qa blockers without needs-human)"
        )
        return
    assert _PASS_STATUS.search(text), (
        f"{path} must have STATUS: PASS or GREEN for M2 close-out"
    )


# ---------------------------------------------------------------------------
# AC: .team/reviews/ APPROVED for T-023-T-033
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticket", _M2_TICKETS)
def test_m2_ticket_review_approved(ticket: str) -> None:
    """Each ticket has an APPROVED review (per-ticket or M2 close-out)."""
    paths = _review_paths_covering(ticket)
    assert paths, (
        f"no .team/reviews/ artifact covering {ticket} "
        f"(need STATUS: APPROVED per-ticket or M2 close-out review)"
    )
    approved = [p for p in paths if _APPROVED.search(p.read_text(encoding="utf-8"))]
    assert approved, (
        f"reviews covering {ticket} exist but none are STATUS: APPROVED: "
        + ", ".join(p.name for p in paths)
    )


# ---------------------------------------------------------------------------
# AC: changelog plain-English M2 summary (ladder + multi-scenario; no $ VOI)
# ---------------------------------------------------------------------------


def test_changelog_has_m2_client_voice_summary() -> None:
    """Changelog has an M2 close-out summary: CTL ladder + multi-scenario."""
    assert _CHANGELOG.is_file(), f"missing {_CHANGELOG}"
    entry = _changelog_m2_closeout_entry()
    assert entry is not None, (
        ".team/changelog.md must include a plain-English M2 close-out summary "
        "(heading mentioning M2 close-out / controller + multi-scenario)"
    )
    lowered = entry.lower()
    assert any(
        tok in lowered for tok in ("ladder", "ordering rule", "ordering baseline")
    ), "M2 changelog summary must mention the CTL / ordering ladder"
    assert any(
        tok in lowered
        for tok in (
            "multi-scenario",
            "multi scenario",
            "information view",
            "p1",
            "b-state",
            "rung 0",
        )
    ), "M2 changelog summary must mention multi-scenario / information views"
    assert not _VOI_DOLLAR_HEADLINE.search(entry), (
        "M2 changelog summary must not carry VOI dollar / VOI-sweep ship headlines"
    )


# ---------------------------------------------------------------------------
# AC: voi/ remains a stub
# ---------------------------------------------------------------------------


def test_voi_package_remains_stub() -> None:
    """voi/ stays empty through M2; M3 may fill it when plan status is COMPLETE."""
    init = _VOI / "__init__.py"
    assert init.is_file(), "expected pre-existing voi package"
    m3_plan = _REPO_ROOT / ".team" / "plans" / "M3-voi-sweep.md"
    m3_complete = m3_plan.is_file() and "Status:** COMPLETE" in m3_plan.read_text(
        encoding="utf-8"
    )
    if m3_complete:
        from blueberries_voi import voi as voi_pkg

        assert voi_pkg.__all__, "M3 COMPLETE expects non-empty voi exports"
        return
    text = init.read_text(encoding="utf-8")
    assert re.search(r"__all__\s*:\s*list\[str\]\s*=\s*\[\s*\]", text), (
        "voi package must remain an empty stub (__all__ == []) until M3"
    )
    extras = [p for p in _VOI.rglob("*.py") if p.name != "__init__.py" and p.is_file()]
    assert not extras, "M2 non-goal: no VOI production modules; found " + ", ".join(
        str(p.relative_to(_REPO_ROOT)) for p in extras
    )


# ---------------------------------------------------------------------------
# AC: no Pyodide / ENG-01 / WASM ship claims in changelog or plan status
# ---------------------------------------------------------------------------


def test_closeout_asserts_no_pyodide_packaging_ship_claims() -> None:
    """Changelog + plan + DoD note must not claim Pyodide/ENG-01/WASM shipped."""
    blobs: list[tuple[str, str]] = []
    entry = _changelog_m2_closeout_entry()
    if entry:
        blobs.append(("changelog M2 summary", entry))
    if _PLAN.is_file():
        blobs.append(("M2 plan", _PLAN.read_text(encoding="utf-8")))
    for path in _closeout_dod_candidates():
        blobs.append((path.name, path.read_text(encoding="utf-8")))

    assert blobs, (
        "Need M2 changelog summary and/or plan/DoD note before asserting "
        "non-claims for Pyodide packaging"
    )

    # Require an explicit non-claim somewhere in close-out surface.
    joined = "\n".join(text for _, text in blobs)
    has_explicit_nonclaim = bool(
        re.search(
            r"(?:no|not|without|non-goal|parked|out of scope).{0,40}"
            r"(?:pyodide|eng-?01|browser\s+packag|wasm|browser\s+demo)",
            joined,
            re.I | re.S,
        )
        or re.search(
            r"(?:pyodide|eng-?01|browser\s+packag|wasm|browser\s+demo).{0,40}"
            r"(?:not\s+(?:in\s+)?(?:scope|m2)|parked|non-goal|not\s+ship)",
            joined,
            re.I | re.S,
        )
    )
    assert has_explicit_nonclaim, (
        "Close-out checklist / changelog / plan must explicitly assert no "
        "Pyodide packaging / ENG-01 browser demo / WASM ship in M2"
    )

    for label, text in blobs:
        for m in _BROWSER_SHIP_CLAIM.finditer(text):
            if _negated_claim_window(text, m.start(), m.end()):
                continue
            pytest.fail(
                f"{label} must not claim Pyodide/ENG-01/WASM shipped: {m.group(0)!r}"
            )


# Relative to ``src/blueberries_voi/``. T-044 slim interactive entry (ADR 0099);
# Pyodide worker / wheel packaging modules remain T-046 / T-047.
_ALLOWED_BROWSER_MODULES: frozenset[str] = frozenset({"browser.py"})


def test_no_browser_or_pyodide_packaging_modules_in_src() -> None:
    """No premature Pyodide/WASM/ENG-01 host modules; T-044 browser.py allowed."""
    hits = (
        list(_SRC.rglob("*browser*"))
        + list(_SRC.rglob("*pyodide*"))
        + list(_SRC.rglob("*eng01*"))
        + list(_SRC.rglob("*wasm*"))
    )
    hits = [
        p
        for p in hits
        if p.is_file()
        and p.suffix == ".py"
        and str(p.relative_to(_SRC)) not in _ALLOWED_BROWSER_MODULES
    ]
    assert not hits, (
        "M2 non-goal: no Pyodide/WASM packaging or premature ENG-01 host "
        f"modules (allowed: {sorted(_ALLOWED_BROWSER_MODULES)}); found "
        + ", ".join(str(p.relative_to(_REPO_ROOT)) for p in hits)
    )


# ---------------------------------------------------------------------------
# AC: PRODUCTION_BACKEND == mean_field
# ---------------------------------------------------------------------------


def test_production_backend_remains_mean_field() -> None:
    """Production age backend lock from T-021 still holds."""
    assert filter_pkg.PRODUCTION_BACKEND == "mean_field"


# ---------------------------------------------------------------------------
# AC: no new runtime dependencies without dedicated ADR
# ---------------------------------------------------------------------------


def test_no_new_runtime_dependencies_for_m2_closeout() -> None:
    """Core runtime deps stay slim (ADR 0101); viz/data stay optional extras."""
    data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    raw = data["project"]["dependencies"]
    names: set[str] = set()
    for spec in raw:
        name = re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip().lower()
        names.add(name)
    assert names == _LOCKED_RUNTIME_DEPS, (
        f"runtime dependencies changed during M2: {sorted(names)} "
        f"(locked {sorted(_LOCKED_RUNTIME_DEPS)}; new deps need a dedicated ADR)"
    )


# ---------------------------------------------------------------------------
# Non-goal / purity locks (controller stays a pure library)
# ---------------------------------------------------------------------------


def test_controller_remains_pure_library() -> None:
    """controller/ has no matplotlib/pyarrow/plotly imports (pure library)."""
    assert _CONTROLLER.is_dir()
    for path in sorted(_CONTROLLER.glob("*.py")):
        bad = _imported_roots(path) & _FORBIDDEN_CONTROLLER_IMPORTS
        assert not bad, f"{path.name} imports forbidden roots: {sorted(bad)}"


# ---------------------------------------------------------------------------
# Process: plan status flipped; backlog records M2 done (on main)
# ---------------------------------------------------------------------------


def test_m2_plan_status_waves_complete() -> None:
    """M2-controller.md status reflects waves complete / close-out done."""
    text = _read(_PLAN)
    head = "\n".join(text.splitlines()[:12])
    assert re.search(
        r"\*\*Status:\*\*\s*.*\b(?:COMPLETE|DONE|CLOSED|CLOSE-?OUT)\b",
        head,
        re.I,
    ), (
        "`.team/plans/M2-controller.md` status line must flip to COMPLETE/DONE "
        "(waves complete) for T-034 close-out"
    )
    # Guard: Wave 7 / T-034 marked done in the plan body.
    assert re.search(r"T-034", text), "plan must still list T-034"
    assert re.search(
        r"(?:Wave\s*7|T-034).{0,80}(?:complete|done|close-?out)",
        text,
        re.I | re.S,
    ) or re.search(
        r"(?:complete|done).{0,80}(?:Wave\s*7|T-034)",
        text,
        re.I | re.S,
    ), "plan body should note Wave 7 / T-034 complete"


def test_backlog_m2_complete_pending_human_merge() -> None:
    """Backlog records M2 complete; library work on main (post-merge accurate)."""
    text = _read(_BACKLOG).lower()
    assert re.search(r"\bm2\b", text), "backlog must mention M2"
    on_main = (
        "f4a467f" in text
        or re.search(
            r"m2\+?m3.{0,80}(library )?(work )?is on [`']?main[`']?",
            text,
            re.I | re.S,
        )
        is not None
        or re.search(
            r"m2.{0,120}(?:complete|done|closed|library).{0,120}on [`']?main[`']?",
            text,
            re.I | re.S,
        )
        is not None
    )
    pending_merge = (
        re.search(
            r"m2.{0,120}(?:complete|done|closed).{0,120}"
            r"(?:pending|awaiting|waiting).{0,80}(?:merge|main)",
            text,
            re.I | re.S,
        )
        is not None
        or re.search(
            r"(?:pending|awaiting|waiting).{0,40}(?:human\s+)?merge.{0,40}main.{0,80}m2",
            text,
            re.I | re.S,
        )
        is not None
    )
    assert on_main or pending_merge, (
        ".team/backlog.md must say M2 library work is on main "
        "(or historically complete pending human merge to main)"
    )
    # Should not still advertise T-034 as the next open work.
    assert not re.search(
        r"next\s*[—\-:].{0,40}t-034",
        text,
        re.I,
    ), "backlog must not still list T-034 as Next"


# ---------------------------------------------------------------------------
# Process: plan §5 DoD checklist copied with items checked
# ---------------------------------------------------------------------------


def test_m2_dod_checklist_copied_and_checked() -> None:
    """Plan §5 Definition of done lives under reviews/ close-out note; checked."""
    assert _PLAN.is_file(), f"missing plan {_PLAN}"
    candidates = _closeout_dod_candidates()
    assert candidates, (
        "Copy plan §5 Definition of done into .team/reviews/ (e.g. M2.md / T-034.md) "
        "or a close-out note with each DoD item checked"
    )

    best: Path | None = None
    best_text = ""
    for path in candidates:
        text = path.read_text(encoding="utf-8")
        if re.search(r"-\s*\[[xX]\]", text) or re.search(
            r"definition of done|DoD", text, re.I
        ):
            best = path
            best_text = text
            break
    assert best is not None and best_text, (
        f"close-out candidates found ({', '.join(p.name for p in candidates)}) "
        "but none contain a checked DoD checklist"
    )

    lowered = best_text.lower()
    missing_themes: list[str] = []
    if "belief" not in lowered and "shelbelief" not in lowered:
        missing_themes.append("Belief API / ShelfBelief")
    if not any(
        tok in lowered for tok in ("ctl-01", "damped", "survival-weighted", "sw")
    ):
        missing_themes.append("CTL-01 damped SW")
    if not any(tok in lowered for tok in ("rollout", "ctl-02", "ctl-04")):
        missing_themes.append("rollout")
    if not any(tok in lowered for tok in ("ladder", "ctl-05")):
        missing_themes.append("ladder")
    if not any(tok in lowered for tok in ("toy dp", "ctl-06", "dp")):
        missing_themes.append("toy DP")
    if not any(tok in lowered for tok in ("multi-scenario", "multi scenario", "p1")):
        missing_themes.append("multi-scenario")
    if "mean_field" not in lowered and "mean-field" not in lowered:
        missing_themes.append("mean_field production")
    if not any(
        tok in lowered for tok in ("voi", "browser", "pyodide", "non-goal", "stub")
    ):
        missing_themes.append("no VOI/browser packaging")

    checked = len(re.findall(r"-\s*\[[xX]\]", best_text))
    unchecked = len(re.findall(r"-\s*\[ \]", best_text))
    assert checked > 0, f"{best} DoD checklist must have checked [x] items"
    assert unchecked == 0, (
        f"{best} still has {unchecked} unchecked DoD items; "
        "all plan §5 items must be [x]"
    )
    assert not missing_themes, (
        f"{best} DoD close-out missing themes: {', '.join(missing_themes)}"
    )


def test_plan_section_5_dod_still_present() -> None:
    """Guard: plan §5 Definition of done section exists for checklist copy source."""
    text = _read(_PLAN)
    assert re.search(r"^##\s+5\.\s+Definition of done", text, re.M), (
        "M2 plan must retain §5 Definition of done as the close-out checklist source"
    )


# ---------------------------------------------------------------------------
# T-034 spec AC marked done at close-out
# ---------------------------------------------------------------------------


def test_t034_spec_acceptance_criteria_checked() -> None:
    """T-034 acceptance-criteria checkboxes are [x] after close-out lands."""
    path = _SPECS / "T-034.md"
    assert path.is_file(), f"missing spec {path}"
    items = _ac_checkboxes(_read(path))
    assert items, "T-034: no acceptance-criteria checkboxes found"
    unchecked = [text for done, text in items if not done]
    assert not unchecked, (
        f"T-034: {len(unchecked)} acceptance criteria still unchecked: "
        + "; ".join(unchecked[:4])
    )
