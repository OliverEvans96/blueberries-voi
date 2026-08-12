"""T-018 M1.5 close-out - RED / Definition-of-Done contract checks.

Asserts plan §9 / `.team/specs/T-018.md` process artifacts exist and are signed.
Does not implement product features; fails until close-out documentation lands.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEAM = _REPO_ROOT / ".team"
_SPECS = _TEAM / "specs"
_QA = _TEAM / "qa"
_REVIEWS = _TEAM / "reviews"
_CHANGELOG = _TEAM / "changelog.md"
_BACKLOG = _TEAM / "backlog.md"
_PLAN = _TEAM / "plans" / "M1.5-filter-complete.md"
_SRC = _REPO_ROOT / "src" / "blueberries_voi"

# Implementation tickets that must be closed for M1.5 DoD (T-018 AC).
_M15_TICKETS: tuple[str, ...] = tuple(f"T-{n:03d}" for n in range(9, 18))

_PASS_STATUS = re.compile(
    r"^STATUS:\s*(?:PASS|GREEN|APPROVED)\b",
    re.IGNORECASE | re.MULTILINE,
)
_RED_STATUS = re.compile(
    r"^STATUS:\s*(?:RED|FAIL|CHANGES[_\s-]?REQUESTED)\b",
    re.IGNORECASE | re.MULTILINE,
)
_APPROVED = re.compile(r"^STATUS:\s*APPROVED\b", re.IGNORECASE | re.MULTILINE)


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


def _oliver_waiver_for(ticket: str) -> bool:
    """True if backlog records an Oliver waiver for this ticket's unfinished AC."""
    if not _BACKLOG.is_file():
        return False
    text = _BACKLOG.read_text(encoding="utf-8")
    # Require ticket id + waiver language + Oliver in the same backlog file.
    if ticket not in text:
        return False
    lowered = text.lower()
    has_waiver = any(
        tok in lowered
        for tok in ("waiv", "oliver note", "oliver-approved", "explicitly waived")
    )
    has_oliver = "oliver" in lowered
    return has_waiver and has_oliver


def _primary_qa(ticket: str) -> Path | None:
    primary = _QA / f"{ticket}.md"
    return primary if primary.is_file() else None


def _review_paths_covering(ticket: str) -> list[Path]:
    """Reviews whose *subject* is this ticket (not incidental body mentions).

    Accepts per-ticket / combined filenames (``T-012.md``, ``T-009-T-010.md``)
    or an APPROVED M1.5 / T-018 close-out review that explicitly lists the ticket
    (or claims coverage of T-009-T-017).
    """
    found: list[Path] = []
    if not _REVIEWS.is_dir():
        return found
    for path in sorted(_REVIEWS.glob("*.md")):
        if path.name == "README.md":
            continue
        stem_tokens = re.findall(r"T-\d{3}", path.stem.upper())
        # Filename match (T-012.md, T-009-T-010.md) via whole ticket tokens.
        if ticket in stem_tokens:
            found.append(path)
            continue
        stem_u = path.stem.upper().replace("_", "-")
        if stem_u not in {"M1.5", "M15", "T-018"}:
            continue
        text = path.read_text(encoding="utf-8")
        if not re.search(r"\bM1\.5\b", text):
            continue
        # Close-out must explicitly cover this ticket or the full T-009-T-017 span.
        covers = bool(
            re.search(rf"\b{re.escape(ticket)}\b", text)
            or re.search(r"T-009\s*[\u2013\u2014\-]\s*T-017", text)
            or re.search(r"T-009\s+through\s+T-017", text, re.I)
            or re.search(r"all of T-009", text, re.I)
        )
        if covers:
            found.append(path)
    return list(dict.fromkeys(found))


def _closeout_dod_candidates() -> list[Path]:
    """Signed plan §9 DoD checklist copies (reviews / team close-out notes only).

    Intentionally excludes ``.team/qa/T-018*.md`` RED maps that *mention* DoD
    without being the signed checklist.
    """
    names = (
        "M1.5.md",
        "M15.md",
        "T-018.md",
        "M1.5-closeout.md",
        "M1.5-dod.md",
        "m15-closeout.md",
    )
    out: list[Path] = []
    for name in names:
        for base in (_REVIEWS, _TEAM):
            p = base / name
            if p.is_file():
                out.append(p)
    # Additional review notes that embed a checked DoD checklist.
    if _REVIEWS.is_dir():
        for p in sorted(_REVIEWS.glob("*.md")):
            if p in out or p.name == "README.md":
                continue
            text = p.read_text(encoding="utf-8")
            if re.search(r"-\s*\[[xX ]\]", text) and re.search(
                r"definition of done|DoD checklist|plan §9|plan § 9", text, re.I
            ):
                out.append(p)
    return list(dict.fromkeys(out))


def _changelog_m15_entry() -> str | None:
    """Return the changelog block that looks like the M1.5 close-out entry."""
    if not _CHANGELOG.is_file():
        return None
    text = _CHANGELOG.read_text(encoding="utf-8")
    # Prefer an explicit M1.5 heading or bullet.
    if re.search(r"^##\s+.*M1\.5", text, re.I | re.M):
        # Capture from that heading to next ## or EOF
        m = re.search(r"^##\s+.*M1\.5.*$", text, re.I | re.M)
        assert m is not None
        rest = text[m.start() :]
        nxt = re.search(r"^##\s+", rest[3:], re.M)
        return rest if nxt is None else rest[: nxt.start() + 3]
    # Single preferred client-facing entry mentioning M1.5
    bullets = []
    for line in text.splitlines():
        if re.search(r"M1\.5|filter complete|data-availability rung", line, re.I):
            bullets.append(line)
    if bullets:
        return "\n".join(bullets)
    return None


# ---------------------------------------------------------------------------
# AC: specs T-009-T-017 acceptance criteria marked done (or Oliver-waived)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticket", _M15_TICKETS)
def test_m15_ticket_spec_acceptance_criteria_done_or_waived(ticket: str) -> None:
    """Each M1.5 implementation ticket's AC checkboxes are [x], or Oliver-waived."""
    path = _SPECS / f"{ticket}.md"
    assert path.is_file(), f"missing spec {path}"
    items = _ac_checkboxes(_read(path))
    assert items, f"{ticket}: no acceptance-criteria checkboxes found"
    unchecked = [text for done, text in items if not done]
    if unchecked and not _oliver_waiver_for(ticket):
        preview = "; ".join(unchecked[:3])
        more = f" (+{len(unchecked) - 3} more)" if len(unchecked) > 3 else ""
        pytest.fail(
            f"{ticket}: {len(unchecked)} acceptance criteria still unchecked "
            f"(or need Oliver waiver in .team/backlog.md): {preview}{more}"
        )


# ---------------------------------------------------------------------------
# AC: .team/qa/ green for M1.5 tickets; no open RED without needs-human
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticket", _M15_TICKETS)
def test_m15_ticket_qa_record_green(ticket: str) -> None:
    """Primary QA record exists and STATUS is PASS/GREEN (not RED)."""
    path = _primary_qa(ticket)
    assert path is not None, (
        f"missing .team/qa/{ticket}.md - M1.5 close-out requires a green QA record"
    )
    text = _read(path)
    if _RED_STATUS.search(text):
        # Allowed only with needs-human escalation recorded.
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
            f"(T-018: no open red qa blockers without needs-human)"
        )
        return
    assert _PASS_STATUS.search(text), (
        f"{path} must have STATUS: PASS or GREEN for M1.5 close-out"
    )


def test_no_open_red_qa_blockers_without_needs_human() -> None:
    """Any RED QA under M1.5 tickets must carry needs-human (file or backlog)."""
    blockers: list[str] = []
    for ticket in _M15_TICKETS:
        path = _primary_qa(ticket)
        if path is None:
            blockers.append(f"{ticket}: missing qa record")
            continue
        text = path.read_text(encoding="utf-8")
        if not _RED_STATUS.search(text):
            continue
        if re.search(r"needs-human", text, re.I):
            continue
        backlog_hit = False
        if _BACKLOG.is_file():
            backlog_hit = bool(
                re.search(
                    rf"{ticket}.*needs-human|needs-human.*{ticket}",
                    _BACKLOG.read_text(encoding="utf-8"),
                    re.I | re.S,
                )
            )
        if not backlog_hit:
            blockers.append(f"{path.name}: RED without needs-human")
    assert not blockers, "Open RED QA blockers: " + "; ".join(blockers)


# ---------------------------------------------------------------------------
# AC: .team/reviews/ APPROVED covering T-009-T-017
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticket", _M15_TICKETS)
def test_m15_ticket_review_approved(ticket: str) -> None:
    """Each ticket has an APPROVED review (per-ticket, combined, or M1.5 close-out)."""
    paths = _review_paths_covering(ticket)
    assert paths, (
        f"no .team/reviews/ artifact covering {ticket} "
        f"(need STATUS: APPROVED per-ticket or M1.5 close-out review)"
    )
    approved = [p for p in paths if _APPROVED.search(p.read_text(encoding="utf-8"))]
    assert approved, (
        f"reviews covering {ticket} exist but none are STATUS: APPROVED: "
        + ", ".join(p.name for p in paths)
    )


# ---------------------------------------------------------------------------
# AC: changelog plain-English M1.5 entry (client voice)
# ---------------------------------------------------------------------------


def test_changelog_has_m15_client_voice_entry() -> None:
    """Changelog has an M1.5 entry: rungs/obs, physics-honest LL, P0/P1 caveats."""
    assert _CHANGELOG.is_file(), f"missing {_CHANGELOG}"
    entry = _changelog_m15_entry()
    assert entry is not None, (
        ".team/changelog.md must include a plain-English M1.5 close-out entry "
        "(prefer one client-facing M1.5 section or bullet)"
    )
    lowered = entry.lower()
    # What the filter can observe per rung
    assert any(
        tok in lowered
        for tok in (
            "rung",
            "observe",
            "observation",
            "p0",
            "p1",
            "mask",
            "data-availability",
            "data availability",
        )
    ), "M1.5 changelog entry must describe what the filter can observe per rung"
    # Likelihood matches sim physics
    assert any(
        tok in lowered
        for tok in (
            "likelihood",
            "physics",
            "day_step",
            "simulator",
            "honest",
            "generative",
        )
    ), "M1.5 changelog entry must say likelihood matches sim physics / honest LL"
    # Honest P0/P1 caveats if Stage A failed there
    assert ("p0" in lowered or "p1" in lowered) and any(
        tok in lowered
        for tok in ("fail", "caveat", "not", "did not", "still", "honest", "negative")
    ), "M1.5 changelog entry must include honest P0/P1 Stage A caveats when applicable"


# ---------------------------------------------------------------------------
# AC: plan §9 DoD checklist copied with each item checked
# ---------------------------------------------------------------------------


def test_dod_checklist_copied_and_checked() -> None:
    """Plan §9 DoD checklist lives under reviews/qa close-out note; items checked."""
    assert _PLAN.is_file(), f"missing plan {_PLAN}"
    candidates = _closeout_dod_candidates()
    assert candidates, (
        "Copy plan §9 Definition of done into .team/reviews/ (e.g. M1.5.md / T-018.md) "
        "or a close-out note with each DoD item checked"
    )

    # Prefer a file that looks like a checklist with [x] markers
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
    # RichObs + masks
    if "richobs" not in lowered and "rich obs" not in lowered:
        missing_themes.append("RichObs")
    if "daylog" not in lowered and "day log" not in lowered:
        missing_themes.append("DayLog")
    if "soft" not in lowered and "heuristic" not in lowered:
        missing_themes.append("soft/heuristic LL removed")
    if "stage c" not in lowered:
        missing_themes.append("Stage C generative")
    if "stage a" not in lowered:
        missing_themes.append("Stage A multi-rung")
    if "stage b" not in lowered and "oracle" not in lowered:
        missing_themes.append("Stage B / oracle")
    if not any(
        tok in lowered
        for tok in ("sliding_window", "l policy", "l fallback", "joint→", "joint->")
    ):
        missing_themes.append("L policy / sliding_window fallback")
    if "ctl" not in lowered and "voi" not in lowered:
        missing_themes.append("no CTL/VOI/browser")
    if "quality" not in lowered and "ruff" not in lowered and "pytest" not in lowered:
        missing_themes.append("quality gates")

    checked = len(re.findall(r"-\s*\[[xX]\]", best_text))
    unchecked = len(re.findall(r"-\s*\[ \]", best_text))
    assert checked > 0, f"{best} DoD checklist must have checked [x] items"
    assert unchecked == 0, (
        f"{best} still has {unchecked} unchecked DoD items; "
        "all plan §9 items must be [x]"
    )
    assert not missing_themes, (
        f"{best} DoD close-out missing themes: {', '.join(missing_themes)}"
    )


# ---------------------------------------------------------------------------
# AC: VOI / browser stay parked; controller may grow under M2 (Wave 1+)
# ---------------------------------------------------------------------------


def test_no_production_ctl_voi_browser_under_m15() -> None:
    """VOI + browser stay stubs; controller may grow under M2 Waves 1-4."""
    controller = _SRC / "controller" / "__init__.py"
    voi = _SRC / "voi" / "__init__.py"
    assert controller.is_file(), "expected pre-existing controller package"
    assert voi.is_file(), "expected pre-existing voi stub"

    voi_text = voi.read_text(encoding="utf-8")
    assert re.search(r"__all__\s*:\s*list\[str\]\s*=\s*\[\s*\]", voi_text), (
        "voi package must remain an empty stub (no VOI sweep API in M1.5/M2)"
    )

    # M2 Waves 1-4 may land ordering / policies / rollout / toy DP; nothing under voi/.
    voi_extras = [
        p
        for p in (_SRC / "voi").rglob("*.py")
        if p.name != "__init__.py" and p.is_file()
    ]
    assert not voi_extras, "non-goal: no VOI production modules; found " + ", ".join(
        str(p.relative_to(_REPO_ROOT)) for p in voi_extras
    )

    ctrl_extras = [
        p
        for p in (_SRC / "controller").rglob("*.py")
        if p.name != "__init__.py" and p.is_file()
    ]
    allowed_ctrl = {
        "ordering.py",
        "rung0.py",
        "damped_sw.py",
        "rollout.py",
        "toy_dp.py",
    }
    unexpected = [p for p in ctrl_extras if p.name not in allowed_ctrl]
    assert not unexpected, (
        "unexpected controller modules (M2 Waves 1-4 allow "
        "ordering/rung0/damped_sw/rollout/toy_dp): "
        + ", ".join(str(p.relative_to(_REPO_ROOT)) for p in unexpected)
    )

    browser_hits = list(_SRC.rglob("*browser*")) + list(_SRC.rglob("*eng01*"))
    assert not browser_hits, "non-goal: no browser modules; found " + ", ".join(
        str(p.relative_to(_REPO_ROOT)) for p in browser_hits
    )


def test_m15_milestone_claims_do_not_assert_ctl_voi_shipped() -> None:
    """Close-out / changelog must not claim CTL or VOI sweep shipped in M1.5."""
    blobs: list[str] = []
    if _CHANGELOG.is_file():
        entry = _changelog_m15_entry()
        if entry:
            blobs.append(entry)
    for path in _closeout_dod_candidates():
        blobs.append(path.read_text(encoding="utf-8"))
    if not blobs:
        pytest.fail(
            "No M1.5 changelog/close-out text yet - required before asserting "
            "non-claims; add changelog M1.5 entry and DoD note first"
        )
    joined = "\n".join(blobs).lower()
    verbs = r"shipped|landed|implemented|added"
    topics = r"ctl|voi sweep|browser"
    claim = re.compile(
        rf"(?:(?:{verbs})\b.{{0,40}}\b(?:{topics})\b|"
        rf"\b(?:{topics})\b.{{0,40}}\b(?:{verbs})\b)",
        re.I | re.S,
    )
    for m in claim.finditer(joined):
        window = joined[max(0, m.start() - 32) : m.end()]
        # Allow non-goal wording: "no CTL … landed", "non-goals: no browser", etc.
        if re.search(r"\b(?:no|not|without|non-goal|never|exclude)\b", window):
            continue
        pytest.fail(
            "M1.5 close-out text must not claim CTL/VOI/browser shipped: "
            f"{m.group(0)!r}"
        )


# ---------------------------------------------------------------------------
# Sanity: plan §9 still lists the DoD we are gating (doc drift guard)
# ---------------------------------------------------------------------------


def test_plan_section_9_dod_still_present() -> None:
    """Guard: plan §9 Definition of done section exists for checklist copy source."""
    text = _read(_PLAN)
    assert re.search(r"^##\s+9\.\s+Definition of done", text, re.M), (
        "M1.5 plan must retain §9 Definition of done as the close-out checklist source"
    )
    for theme in ("RichObs", "DayLog", "Stage C", "Stage A", "sliding_window"):
        assert theme in text, (
            f"plan §9 / plan body missing expected DoD theme {theme!r}"
        )
