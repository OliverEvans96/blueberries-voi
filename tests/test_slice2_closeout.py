"""T-052 Slice 2 close-out — RED / Definition-of-Done contract checks.

Asserts ENG-01 Slice-2 (T-049–T-051) process artifacts and non-goals from
``.team/specs/T-052.md`` / ``.team/plans/ENG-01-dual-runtime.md``.
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
_PLAN = _TEAM / "plans" / "ENG-01-dual-runtime.md"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

# Slice-2 tickets that must be closed for T-052 DoD (spec AC: T-049–T-051).
_SLICE2_QA_TICKETS: tuple[str, ...] = ("T-049", "T-050", "T-051")
# Implement tickets with APPROVED review + verify PASS (parent brief).
_SLICE2_IMPLEMENT_TICKETS: tuple[str, ...] = ("T-050", "T-051")

_PASS_STATUS = re.compile(
    r"^STATUS:\s*(?:\*\*)?(?:PASS|GREEN|APPROVED|DONE)(?:\*\*)?\b",
    re.IGNORECASE | re.MULTILINE,
)
_RED_STATUS = re.compile(
    r"^STATUS:\s*(?:\*\*)?(?:RED|FAIL|CHANGES[_\s-]?REQUESTED)(?:\*\*)?\b",
    re.IGNORECASE | re.MULTILINE,
)
_APPROVED = re.compile(
    r"^STATUS:\s*(?:\*\*)?APPROVED(?:\*\*)?\b",
    re.IGNORECASE | re.MULTILINE,
)

# Non-goal / contract themes required on the Slice-2 close-out checklist.
_CHECKLIST_THEMES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "API responses share Snapshot/DayDelta with Pyodide",
        (
            "snapshot",
            "daydelta",
            "day delta",
            "pyodide",
            "same",
            "share",
            "parity",
            "adr 0098",
            "0098",
        ),
    ),
    (
        "do not claim production multi-tenant hosting",
        (
            "multi-tenant",
            "multitenant",
            "multi tenant",
            "production host",
            "production hosting",
            "not production",
            "non-production",
            "local dev",
            "dev path",
            "development host",
        ),
    ),
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


def _verify_qa(ticket: str) -> Path | None:
    verify = _QA / f"{ticket}-verify.md"
    return verify if verify.is_file() else None


def _ticket_qa_notes_green(ticket: str) -> tuple[bool, str]:
    """Return (ok, detail) if primary QA or verify note records green/DONE."""
    details: list[str] = []
    primary = _primary_qa(ticket)
    if primary is not None:
        text = primary.read_text(encoding="utf-8")
        if _PASS_STATUS.search(text) and not _RED_STATUS.search(text):
            return True, f"{primary.name} PASS/GREEN/DONE"
        details.append(f"{primary.name} not green (STATUS still RED or missing PASS)")
    else:
        details.append(f"missing .team/qa/{ticket}.md")

    verify = _verify_qa(ticket)
    if verify is not None:
        text = verify.read_text(encoding="utf-8")
        if _PASS_STATUS.search(text) and not _RED_STATUS.search(text):
            return True, f"{verify.name} PASS"
        details.append(f"{verify.name} present but not PASS")
    else:
        details.append(f"missing .team/qa/{ticket}-verify.md")

    # Aggregated Slice-2 / ENG-01 close-out QA may mark the ticket DONE.
    for agg_name in (
        "T-052.md",
        "ENG-01-slice2.md",
        "Slice2.md",
        "slice2.md",
        "ENG-01-Slice2.md",
    ):
        agg = _QA / agg_name
        if not agg.is_file():
            continue
        text = agg.read_text(encoding="utf-8")
        if re.search(
            rf"\b{re.escape(ticket)}\b.{{0,120}}"
            r"(?:PASS|GREEN|DONE|verify-green|verify green)",
            text,
            re.I | re.S,
        ) or re.search(
            rf"(?:PASS|GREEN|DONE|verify-green).{{0,120}}\b{re.escape(ticket)}\b",
            text,
            re.I | re.S,
        ):
            if _RED_STATUS.search(text) and agg_name == "T-052.md":
                # T-052 RED during qa phase does not count as green for children.
                continue
            return True, f"{agg.name} lists {ticket} green/DONE"

    return False, "; ".join(details)


def _review_paths_covering(ticket: str) -> list[Path]:
    """Reviews whose subject is this ticket or Slice-2 / ENG-01 close-out."""
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
        if stem_u not in {
            "T-052",
            "SLICE2",
            "SLICE-2",
            "ENG-01-SLICE2",
            "ENG-01-SLICE-2",
            "ENG01-SLICE2",
            "ENG-01",
        }:
            continue
        text = path.read_text(encoding="utf-8")
        covers = bool(
            re.search(rf"\b{re.escape(ticket)}\b", text)
            or re.search(r"T-049\s*[\u2013\u2014\-]\s*T-051", text)
            or re.search(r"T-050\s*[\u2013\u2014\-]\s*T-051", text)
            or re.search(r"T-050\s+through\s+T-051", text, re.I)
            or re.search(r"Slice\s*2", text, re.I)
        )
        if covers:
            found.append(path)
    return found


def _closeout_checklist_candidates() -> list[Path]:
    """Close-out notes expected to carry Slice-2 contract / non-goal locks.

    Only named Slice-2 / T-052 / ENG-01 close-out files. ``.team/qa/T-052.md``
    counts only when it is no longer RED (so the qa RED map cannot satisfy the
    checklist). Historical M1.5/M2/M3/Slice-1 DoD notes are intentionally excluded.
    """
    names = (
        "ENG-01-slice2.md",
        "ENG-01-Slice2.md",
        "Slice2.md",
        "slice2.md",
        "T-052.md",
        "ENG-01.md",
    )
    out: list[Path] = []
    for name in names:
        for base in (_REVIEWS, _QA):
            path = base / name
            if not path.is_file():
                continue
            if base == _QA and name == "T-052.md":
                text = path.read_text(encoding="utf-8")
                if _RED_STATUS.search(text):
                    continue
            out.append(path)
    return list(dict.fromkeys(out))


def _changelog_slice2_entry() -> str | None:
    """Return the changelog block that looks like the Slice-2 / API close-out."""
    if not _CHANGELOG.is_file():
        return None
    text = _CHANGELOG.read_text(encoding="utf-8")
    heading = re.search(
        r"^##\s+.*(Slice\s*2|local\s+HTTP|HTTP\s+API|ASGI|API\s+\(dev\)|"
        r"developers?\s+can).*$",
        text,
        re.I | re.M,
    )
    if heading is not None:
        rest = text[heading.start() :]
        nxt = re.search(r"^##\s+", rest[3:], re.M)
        block = rest if nxt is None else rest[: nxt.start() + 3]
        if re.search(
            r"http|api|local|simulator|engine|developer",
            block,
            re.I,
        ):
            return block

    bullets: list[str] = []
    for line in text.splitlines():
        if re.search(
            r"(?:Slice\s*2|local\s+HTTP|HTTP\s+API|drive.{0,40}simulator|"
            r"developers?.{0,40}(?:HTTP|API)|T-052)",
            line,
            re.I,
        ):
            bullets.append(line)
    if bullets:
        return "\n".join(bullets)
    return None


def _negated_claim_window(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 64) : end + 24]
    return bool(
        re.search(
            r"\b(?:no|not|without|non-goal|never|exclude|out of scope|"
            r"do not|don't|asserts?\s+no|not\s+required|do\s+not\s+claim)\b",
            window,
            re.I,
        )
    )


# ---------------------------------------------------------------------------
# AC: QA notes mark T-049–T-051 DONE / green
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticket", _SLICE2_QA_TICKETS)
def test_slice2_ticket_qa_or_verify_green(ticket: str) -> None:
    """Each Slice-2 ticket has green primary QA and/or verify PASS note."""
    ok, detail = _ticket_qa_notes_green(ticket)
    assert ok, (
        f"{ticket}: Slice-2 close-out requires green/DONE qa notes "
        f"(primary PASS or {ticket}-verify.md PASS, or T-052/ENG-01-slice2 "
        f"listing the ticket DONE): {detail}"
    )


@pytest.mark.parametrize("ticket", _SLICE2_IMPLEMENT_TICKETS)
def test_slice2_ticket_verify_pass_artifact_present(ticket: str) -> None:
    """Each Slice-2 implement ticket has a verifier PASS artifact under .team/qa/."""
    path = _verify_qa(ticket)
    assert path is not None, (
        f"missing .team/qa/{ticket}-verify.md — copy from team/{ticket}/verify tip"
    )
    text = _read(path)
    assert _PASS_STATUS.search(text), (
        f"{path} must have STATUS: PASS for Slice-2 close-out"
    )
    assert not _RED_STATUS.search(text), f"{path} must not be RED/FAIL"


# ---------------------------------------------------------------------------
# DoD / parent: .team/reviews/ APPROVED for T-050–T-051
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticket", _SLICE2_IMPLEMENT_TICKETS)
def test_slice2_ticket_review_approved(ticket: str) -> None:
    """Each implement ticket has an APPROVED review (per-ticket or Slice-2 close-out)."""
    paths = _review_paths_covering(ticket)
    assert paths, (
        f"no .team/reviews/ artifact covering {ticket} "
        f"(need STATUS: APPROVED per-ticket or Slice-2 close-out review; "
        f"copy from team/{ticket}/review)"
    )
    approved = [p for p in paths if _APPROVED.search(p.read_text(encoding="utf-8"))]
    assert approved, (
        f"reviews covering {ticket} exist but none are STATUS: APPROVED: "
        + ", ".join(p.name for p in paths)
    )


# ---------------------------------------------------------------------------
# AC: changelog plain-English local HTTP API entry (client voice)
# ---------------------------------------------------------------------------


def test_changelog_has_slice2_client_voice_entry() -> None:
    """Changelog: developers drive the same simulator engine over a local HTTP API."""
    assert _CHANGELOG.is_file(), f"missing {_CHANGELOG}"
    entry = _changelog_slice2_entry()
    assert entry is not None, (
        ".team/changelog.md must include a plain-English Slice-2 entry "
        "(developers / local HTTP API / same simulator engine; T-052)"
    )
    lowered = entry.lower()
    assert any(
        tok in lowered
        for tok in (
            "developer",
            "developers",
            "you can",
            "local",
        )
    ), "Slice-2 changelog entry must speak to developers / local use (client voice)"
    assert any(
        tok in lowered
        for tok in (
            "http",
            "api",
            "asgi",
        )
    ), "Slice-2 changelog entry must mention the local HTTP / API path"
    assert any(
        tok in lowered
        for tok in (
            "simulator",
            "engine",
            "same",
        )
    ), "Slice-2 changelog entry must mention the (same) simulator engine"
    assert any(
        tok in lowered
        for tok in (
            "iteration",
            "iterate",
            "local",
            "dev",
            "development",
            "drive",
        )
    ), "Slice-2 changelog entry must mention iteration / local drive use"
    # Client-voice: avoid a jargon-only bullet (OpenAPI / TestClient alone).
    jargon_only = bool(
        re.search(r"\b(?:openapi|testclient|asgi|fastapi|starlette)\b", entry, re.I)
    ) and not any(
        tok in lowered
        for tok in (
            "developer",
            "you can",
            "drive",
            "local",
            "iterate",
            "iteration",
            "simulator",
        )
    )
    assert not jargon_only, (
        "Slice-2 changelog must be client-voice (what developers can do), "
        "not jargon-only (OpenAPI/TestClient alone)"
    )


# ---------------------------------------------------------------------------
# AC: checklist asserts Snapshot/DayDelta parity + no multi-tenant claim
# ---------------------------------------------------------------------------


def test_slice2_closeout_contract_checklist() -> None:
    """Close-out checklist: shared Snapshot/DayDelta; no production multi-tenant claim."""
    candidates = _closeout_checklist_candidates()
    assert candidates, (
        "Add a Slice-2 close-out checklist under .team/reviews/ "
        "(e.g. ENG-01-slice2.md / T-052.md) asserting Snapshot/DayDelta parity "
        "with Pyodide and no production multi-tenant hosting claim"
    )

    best: Path | None = None
    best_text = ""
    best_hits = -1
    for path in candidates:
        text = path.read_text(encoding="utf-8")
        hits = 0
        for _label, tokens in _CHECKLIST_THEMES:
            if any(tok in text.lower() for tok in tokens):
                hits += 1
        if hits > best_hits:
            best_hits = hits
            best = path
            best_text = text

    assert best is not None and best_text, "no close-out candidate readable"
    lowered = best_text.lower()

    # Theme 1: shared Snapshot / DayDelta with Pyodide (positive parity claim).
    has_snapshot = "snapshot" in lowered
    has_day_delta = "daydelta" in lowered or "day delta" in lowered
    has_pyodide_or_share = any(
        tok in lowered
        for tok in ("pyodide", "share", "same", "parity", "both runtimes", "0098")
    )
    assert has_snapshot and has_day_delta and has_pyodide_or_share, (
        f"{best} must assert API responses share Snapshot/DayDelta with Pyodide "
        "(name both schemas and the shared / Pyodide parity)"
    )

    # Theme 2: explicit non-claim for production multi-tenant hosting.
    multi_tenant_ok = False
    for tok in (
        "multi-tenant",
        "multitenant",
        "multi tenant",
        "production host",
        "production hosting",
        "production multi",
    ):
        for m in re.finditer(re.escape(tok), lowered):
            if _negated_claim_window(best_text, m.start(), m.end()):
                multi_tenant_ok = True
                break
        if multi_tenant_ok:
            break
    if not multi_tenant_ok and re.search(
        r"-\s*\[[xX]\].{0,160}(?:multi-?tenant|production\s+host|"
        r"not\s+production|non-production|local\s+dev)",
        best_text,
        re.I | re.S,
    ):
        multi_tenant_ok = True
    assert multi_tenant_ok, (
        f"{best} must explicitly assert no production multi-tenant hosting claim "
        "(checked non-goal or nearby negation)"
    )

    checked = len(re.findall(r"-\s*\[[xX]\]", best_text))
    assert checked > 0, (
        f"{best} must include checked [x] contract / non-goal checklist items"
    )


# ---------------------------------------------------------------------------
# AC: plan Slice-2 waves marked complete
# ---------------------------------------------------------------------------


def test_eng01_plan_slice2_waves_complete() -> None:
    """ENG-01 plan status / Slice-2 waves marked complete at close-out."""
    text = _read(_PLAN)
    head = "\n".join(text.splitlines()[:16])
    # Ticket-map rows like "T-052 Slice-2 close-out" must NOT count as done.
    status_ok = bool(
        re.search(
            r"\*\*Status:\*\*\s*.*\b(?:COMPLETE|DONE|CLOSED|"
            r"Slice\s*2\s+(?:complete|done|closed)|"
            r"waves?\s+(?:0-2|1-2)\s+complete)\b",
            head,
            re.I,
        )
    )
    body_ok = bool(
        re.search(
            r"Slice\s*2.{0,80}(?:waves?\s+)?(?:are\s+|is\s+|marked\s+)?"
            r"(?:complete|done|closed)",
            text,
            re.I | re.S,
        )
        or re.search(
            r"(?:Wave\s*2|T-052).{0,60}(?:marked\s+)?(?:complete|done|closed)"
            r"(?!\s*-?\s*out\b)",
            text,
            re.I | re.S,
        )
        or re.search(
            r"(?:complete|done|closed).{0,60}(?:Slice\s*2|Wave\s*2\s+.*API)",
            text,
            re.I | re.S,
        )
    )
    assert status_ok or body_ok, (
        "`.team/plans/ENG-01-dual-runtime.md` must mark Slice-2 waves complete "
        "(status line COMPLETE/DONE or an explicit Slice 2 / Wave 2 complete note; "
        "the T-052 'close-out' ticket title alone is not enough)"
    )
    # Guard: still lists Slice 2 ticket map.
    assert re.search(r"T-052", text), "plan must still list T-052"
    assert re.search(r"Slice\s*2", text, re.I), "plan must still mention Slice 2"


# ---------------------------------------------------------------------------
# AC: no merge to main by agents (process lock)
# ---------------------------------------------------------------------------


def test_slice2_pending_human_merge_not_merged_by_agents() -> None:
    """Backlog/reviews: Slice-2 done pending human merge; agents did not merge."""
    blobs: list[tuple[str, str]] = []
    if _BACKLOG.is_file():
        blobs.append(("backlog", _BACKLOG.read_text(encoding="utf-8")))
    if _REVIEWS.is_dir():
        for path in sorted(_REVIEWS.glob("*.md")):
            if path.name == "README.md":
                continue
            stem_u = path.stem.upper().replace("_", "-")
            if stem_u in {
                "T-052",
                "SLICE2",
                "SLICE-2",
                "ENG-01-SLICE2",
                "ENG-01-SLICE-2",
                "ENG-01",
            } or re.search(r"slice\s*2", path.read_text(encoding="utf-8")[:400], re.I):
                blobs.append((path.name, path.read_text(encoding="utf-8")))
    assert blobs, "need backlog and/or Slice-2 reviews close-out note for merge lock"

    # Ignore historical M2/M3/Slice-1 "pending human merge" lines unless they bind Slice-2.
    slice2_pending = False
    for label, text in blobs:
        if re.search(
            r"(?:slice\s*2|t-052).{0,120}"
            r"(?:complete|done|closed|green).{0,120}"
            r"(?:pending|awaiting|waiting).{0,80}(?:human\s+)?merge",
            text,
            re.I | re.S,
        ) or re.search(
            r"(?:slice\s*2|t-052|eng-?01\s+slice\s*2|api\s+slice).{0,80}"
            r"(?:pending|awaiting|waiting).{0,80}(?:human\s+)?merge",
            text,
            re.I | re.S,
        ):
            slice2_pending = True
            break
        if label == "backlog" and re.search(
            r"Done\s*[\-\u2013\u2014]\s*(?:ENG-01\s+)?Slice\s*2.{0,160}"
            r"(?:pending|awaiting|waiting).{0,80}(?:human\s+)?merge",
            text,
            re.I | re.S,
        ):
            slice2_pending = True
            break

    assert slice2_pending, (
        ".team/backlog.md or a Slice-2 reviews close-out note must record that "
        "Slice-2 / T-052 is complete pending human merge to main "
        "(M2/M3/Slice-1 pending-merge lines alone do not satisfy this AC)"
    )


# ---------------------------------------------------------------------------
# Process: do not weaken CI gates
# ---------------------------------------------------------------------------


def test_ci_quality_gates_not_weakened() -> None:
    """Coverage floor and mypy strict remain locked (T-052: do not weaken CI)."""
    text = _read(_PYPROJECT)
    assert re.search(r"--cov-fail-under\s*=\s*80\b", text), (
        "pyproject.toml must keep --cov-fail-under=80"
    )
    assert re.search(r"(?m)^strict\s*=\s*true\s*$", text), (
        "pyproject.toml [tool.mypy] must keep strict = true"
    )


# ---------------------------------------------------------------------------
# T-052 spec AC marked done at close-out
# ---------------------------------------------------------------------------


def test_t052_spec_acceptance_criteria_checked() -> None:
    """T-052 acceptance-criteria checkboxes are [x] after close-out lands."""
    path = _SPECS / "T-052.md"
    assert path.is_file(), f"missing spec {path}"
    items = _ac_checkboxes(_read(path))
    assert items, "T-052: no acceptance-criteria checkboxes found"
    unchecked = [text for done, text in items if not done]
    assert not unchecked, (
        f"T-052: {len(unchecked)} acceptance criteria still unchecked: "
        + "; ".join(unchecked[:4])
    )
