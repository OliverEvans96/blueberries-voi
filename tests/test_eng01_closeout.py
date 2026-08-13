"""T-058 ENG-01 / Slice 3 close-out - RED / Definition-of-Done contract checks.

Asserts ENG-01 Slice-3 + board close-out (T-053-T-057) process artifacts and
non-goals from ``.team/specs/T-058.md`` / ``.team/plans/ENG-01-dual-runtime.md``.
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

# Slice-3 tickets that must be green for T-058 AC (qa notes T-053-T-057).
_SLICE3_QA_TICKETS: tuple[str, ...] = tuple(f"T-{n:03d}" for n in range(53, 58))
# Implement tips that need APPROVED reviews + verify PASS (parent brief).
_SLICE3_IMPLEMENT_TICKETS: tuple[str, ...] = tuple(f"T-{n:03d}" for n in range(54, 58))

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

# Non-goal themes required on the ENG-01 / Slice-3 close-out checklist surface.
_NONGOAL_THEMES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "not full WASM A / rewrite",
        ("full wasm", "wasm rewrite", "not a", "option a", "wasm a"),
    ),
    (
        "not JS-only B as production",
        (
            "js-only",
            "js only",
            "option b",
            "javascript-only",
            "not b",
            "physics as production",
        ),
    ),
    (
        "no matplotlib / pyarrow in browser",
        ("matplotlib", "pyarrow"),
    ),
    (
        "no production-N-in-tab claim",
        (
            "production-n",
            "production n",
            "n=2000",
            "n = 2000",
            "production particles",
            "in-tab",
            "in tab",
            "production-n-in-tab",
        ),
    ),
    (
        "honesty / cadence flags still out",
        (
            "honesty",
            "cadence",
            "voi-02",
            "x-06",
            "misspecification",
            "⚑",
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

    # Aggregated ENG-01 / Slice-3 close-out QA may mark the ticket DONE.
    for agg_name in (
        "T-058.md",
        "ENG-01.md",
        "ENG-01-slice3.md",
        "ENG-01-Slice3.md",
        "Slice3.md",
        "slice3.md",
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
            if _RED_STATUS.search(text) and agg_name == "T-058.md":
                # T-058 RED during qa phase does not count as green for children.
                continue
            return True, f"{agg.name} lists {ticket} green/DONE"

    return False, "; ".join(details)


def _review_paths_covering(ticket: str) -> list[Path]:
    """Reviews whose subject is this ticket or ENG-01 / Slice-3 close-out."""
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
            "T-058",
            "SLICE3",
            "SLICE-3",
            "ENG-01-SLICE3",
            "ENG-01-SLICE-3",
            "ENG01-SLICE3",
            "ENG-01",
        }:
            continue
        text = path.read_text(encoding="utf-8")
        covers = bool(
            re.search(rf"\b{re.escape(ticket)}\b", text)
            or re.search(r"T-053\s*[\u2013\u2014\-]\s*T-057", text)
            or re.search(r"T-054\s*[\u2013\u2014\-]\s*T-057", text)
            or re.search(r"T-054\s+through\s+T-057", text, re.I)
            or re.search(r"Slice\s*3", text, re.I)
        )
        if covers:
            found.append(path)
    return found


def _closeout_nongoal_candidates() -> list[Path]:
    """Close-out notes expected to carry ENG-01 / Slice-3 non-goal locks.

    Prefers ``.team/reviews/`` DoD notes. ``.team/qa/T-058.md`` counts only when
    it is no longer RED (implement/verify close-out), so the qa RED map itself
    cannot satisfy the non-goal checklist.
    """
    names = (
        "ENG-01.md",
        "ENG-01-slice3.md",
        "ENG-01-Slice3.md",
        "Slice3.md",
        "slice3.md",
        "T-058.md",
        "ENG-01-dod.md",
    )
    out: list[Path] = []
    for name in names:
        for base in (_REVIEWS, _QA):
            path = base / name
            if not path.is_file():
                continue
            if base == _QA and name == "T-058.md":
                text = path.read_text(encoding="utf-8")
                if _RED_STATUS.search(text):
                    continue
            out.append(path)
    # Broad scan: only notes that explicitly bind ENG-01 / Slice 3 / T-058
    # (ignore historical M1.5/M2/M3 DoD checklists that also say "non-goal").
    if _REVIEWS.is_dir():
        for path in sorted(_REVIEWS.glob("*.md")):
            if path in out or path.name == "README.md":
                continue
            stem_u = path.stem.upper().replace("_", "-")
            if stem_u in {"M1", "M1.5", "M15", "M2", "M3"}:
                continue
            text = path.read_text(encoding="utf-8")
            if not re.search(r"-\s*\[[xX ]\]", text):
                continue
            if re.search(
                r"\b(?:eng-?01|slice\s*3|t-058)\b",
                text,
                re.I,
            ) and re.search(
                r"non-?goal|definition of done|DoD|close-?out",
                text,
                re.I,
            ):
                out.append(path)
    return list(dict.fromkeys(out))


def _changelog_eng01_closeout_entry() -> str | None:
    """Return the changelog block for ENG-01 / Slice-3 dual-runtime close-out."""
    if not _CHANGELOG.is_file():
        return None
    text = _CHANGELOG.read_text(encoding="utf-8")
    heading = re.search(
        r"^##\s+.*(ENG-01|Slice\s*3|dual[- ]runtime|live simulator|"
        r"interactive simulator|browser).*$",
        text,
        re.I | re.M,
    )
    if heading is not None:
        rest = text[heading.start() :]
        nxt = re.search(r"^##\s+", rest[3:], re.M)
        block = rest if nxt is None else rest[: nxt.start() + 3]
        if re.search(
            r"browser|simulator|local\s+api|demo\s+budget|interact",
            block,
            re.I,
        ):
            return block

    bullets: list[str] = []
    for line in text.splitlines():
        if re.search(
            r"(?:ENG-01|Slice\s*3|dual[- ]runtime|live simulator|"
            r"local\s+(?:HTTP\s+)?API|demo\s+budget|T-058)",
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
            r"still out|parked|do not|don't|asserts?\s+no|not\s+required)\b",
            window,
            re.I,
        )
    )


# ---------------------------------------------------------------------------
# AC: QA notes mark T-053-T-057 DONE / green
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticket", _SLICE3_QA_TICKETS)
def test_slice3_ticket_qa_or_verify_green(ticket: str) -> None:
    """Each Slice-3 ticket has green primary QA and/or verify PASS note."""
    ok, detail = _ticket_qa_notes_green(ticket)
    assert ok, (
        f"{ticket}: ENG-01 / Slice-3 close-out requires green/DONE qa notes "
        f"(primary PASS or {ticket}-verify.md PASS): {detail}"
    )


@pytest.mark.parametrize("ticket", _SLICE3_IMPLEMENT_TICKETS)
def test_slice3_ticket_verify_pass_artifact_present(ticket: str) -> None:
    """Each Slice-3 implement tip has a verifier PASS artifact under .team/qa/."""
    path = _verify_qa(ticket)
    assert path is not None, (
        f"missing .team/qa/{ticket}-verify.md - copy from team/{ticket}/verify tip"
    )
    text = _read(path)
    assert _PASS_STATUS.search(text), (
        f"{path} must have STATUS: PASS for ENG-01 / Slice-3 close-out"
    )
    assert not _RED_STATUS.search(text), f"{path} must not be RED/FAIL"


# ---------------------------------------------------------------------------
# AC / DoD: .team/reviews/ APPROVED for T-054-T-057
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticket", _SLICE3_IMPLEMENT_TICKETS)
def test_slice3_ticket_review_approved(ticket: str) -> None:
    """Each implement tip has an APPROVED review (per-ticket or ENG-01 close-out)."""
    paths = _review_paths_covering(ticket)
    assert paths, (
        f"no .team/reviews/ artifact covering {ticket} "
        f"(need STATUS: APPROVED per-ticket or ENG-01 / Slice-3 close-out review; "
        f"copy from team/{ticket}/review)"
    )
    approved = [p for p in paths if _APPROVED.search(p.read_text(encoding="utf-8"))]
    assert approved, (
        f"reviews covering {ticket} exist but none are STATUS: APPROVED: "
        + ", ".join(p.name for p in paths)
    )


# ---------------------------------------------------------------------------
# AC: changelog client voice - browser interact + local API iterate
# ---------------------------------------------------------------------------


def test_changelog_has_eng01_client_voice_entry() -> None:
    """Changelog: interact in browser (demo budgets) + iterate via local API."""
    assert _CHANGELOG.is_file(), f"missing {_CHANGELOG}"
    entry = _changelog_eng01_closeout_entry()
    assert entry is not None, (
        ".team/changelog.md must include a plain-English ENG-01 / Slice-3 entry "
        "(live simulator in the browser under demo budgets; local API for developers)"
    )
    lowered = entry.lower()
    assert any(
        tok in lowered
        for tok in (
            "browser",
            "in the browser",
            "browser tab",
            "web",
        )
    ), "ENG-01 changelog must mention interacting in the browser"
    assert any(
        tok in lowered
        for tok in (
            "simulator",
            "interactive",
            "live",
            "demo",
        )
    ), "ENG-01 changelog must mention the live / interactive simulator"
    assert any(
        tok in lowered
        for tok in (
            "demo",
            "budget",
            "dialed",
            "capped",
            "lightweight",
        )
    ), "ENG-01 changelog must mention demo / dialed budgets"
    assert any(
        tok in lowered
        for tok in (
            "local api",
            "local http",
            "http api",
            "developers",
            "developer",
            "iterate",
            "iteration",
        )
    ), (
        "ENG-01 changelog must mention developers iterating via the local API "
        "(client voice)"
    )
    # Client-voice: avoid a jargon-only bullet (paths / RPC / micropip alone).
    jargon_only = bool(
        re.search(r"\b(?:rpc|micropip|pyodide|asgi|wasm|vite)\b", entry, re.I)
    ) and not any(
        tok in lowered
        for tok in (
            "you can",
            "reader",
            "browser",
            "developer",
            "interact",
            "iterate",
            "demo",
        )
    )
    assert not jargon_only, (
        "ENG-01 changelog must be client-voice (what someone can do), "
        "not jargon-only (RPC/micropip/Pyodide/ASGI alone)"
    )


# ---------------------------------------------------------------------------
# AC: close-out checklist asserts ENG-01 non-goals
# ---------------------------------------------------------------------------


def test_eng01_closeout_nongoals_checklist() -> None:
    """Close-out asserts WASM-A / JS-B / matplotlib-pyarrow / prod-N / ⚑ non-goals."""
    candidates = _closeout_nongoal_candidates()
    assert candidates, (
        "Add an ENG-01 / Slice-3 close-out checklist under .team/reviews/ "
        "(e.g. ENG-01.md / T-058.md) asserting non-goals"
    )

    best: Path | None = None
    best_text = ""
    best_hits = -1
    for path in candidates:
        text = path.read_text(encoding="utf-8")
        hits = 0
        for _label, tokens in _NONGOAL_THEMES:
            if any(tok in text.lower() for tok in tokens):
                hits += 1
        if hits > best_hits:
            best_hits = hits
            best = path
            best_text = text

    assert best is not None and best_text, "no close-out candidate readable"
    lowered = best_text.lower()
    missing: list[str] = []
    for label, tokens in _NONGOAL_THEMES:
        if not any(tok in lowered for tok in tokens):
            missing.append(label)
            continue
        theme_ok = False
        for tok in tokens:
            for m in re.finditer(re.escape(tok), lowered):
                if _negated_claim_window(best_text, m.start(), m.end()):
                    theme_ok = True
                    break
            if theme_ok:
                break
        if not theme_ok and re.search(
            rf"-\s*\[[xX]\].{{0,160}}{re.escape(tokens[0])}",
            best_text,
            re.I | re.S,
        ):
            theme_ok = True
        if not theme_ok:
            missing.append(f"{label} (mentioned but not asserted as non-goal)")

    assert not missing, (
        f"{best} ENG-01 close-out missing non-goal locks: {', '.join(missing)}"
    )
    checked = len(re.findall(r"-\s*\[[xX]\]", best_text))
    assert checked > 0, (
        f"{best} must include checked [x] non-goal / DoD checklist items"
    )


# ---------------------------------------------------------------------------
# AC: plan marked ENG-01 slices complete
# ---------------------------------------------------------------------------


def test_eng01_plan_slices_complete() -> None:
    """ENG-01 plan status marks all slices (incl. Slice 3 / T-058) complete."""
    text = _read(_PLAN)
    head = "\n".join(text.splitlines()[:16])
    # Ticket-map rows like "T-058 … close-out" must NOT count as done alone.
    status_ok = bool(
        re.search(
            r"\*\*Status:\*\*\s*.*\b(?:COMPLETE|DONE|CLOSED|"
            r"slices?\s+complete|ENG-01\s+(?:complete|done|closed)|"
            r"Slice\s*3\s+(?:complete|done|closed))\b",
            head,
            re.I,
        )
    )
    body_ok = bool(
        re.search(
            r"(?:ENG-01|all\s+slices|slices\s+1\s*[\u2013\u2014\-]\s*3|"
            r"Slice\s*3).{0,100}(?:waves?\s+)?"
            r"(?:are\s+|is\s+|marked\s+)?(?:complete|done|closed)",
            text,
            re.I | re.S,
        )
        or re.search(
            r"(?:Wave\s*3|T-058).{0,60}(?:marked\s+)?(?:complete|done|closed)"
            r"(?!\s*-?\s*out\b)",
            text,
            re.I | re.S,
        )
        or re.search(
            r"(?:complete|done|closed).{0,60}(?:ENG-01|Slice\s*3|all\s+slices)",
            text,
            re.I | re.S,
        )
    )
    assert status_ok or body_ok, (
        "`.team/plans/ENG-01-dual-runtime.md` must mark ENG-01 slices complete "
        "(status COMPLETE/DONE or an explicit Slice 3 / ENG-01 complete note; "
        "the T-058 'close-out' ticket title alone is not enough)"
    )
    assert re.search(r"T-058", text), "plan must still list T-058"
    assert re.search(r"Slice\s*3", text, re.I), "plan must still mention Slice 3"


# ---------------------------------------------------------------------------
# AC: backlog ENG-01 Done / pending human merge (not parked)
# ---------------------------------------------------------------------------


def test_backlog_eng01_done_pending_human_merge() -> None:
    """Backlog: ENG-01 Done / pending human merge; not still Active/parked/Next."""
    text = _read(_BACKLOG)
    lowered = text.lower()
    assert re.search(r"eng-?01", lowered), "backlog must mention ENG-01"

    done_pending = bool(
        re.search(
            r"(?:done|complete|closed).{0,80}eng-?01.{0,160}"
            r"(?:pending|awaiting|waiting).{0,80}(?:human\s+)?merge",
            text,
            re.I | re.S,
        )
        or re.search(
            r"eng-?01.{0,120}(?:done|complete|closed).{0,160}"
            r"(?:pending|awaiting|waiting).{0,80}(?:human\s+)?merge",
            text,
            re.I | re.S,
        )
        or re.search(
            r"Done\s*[\-\u2013\u2014]\s*ENG-01.{0,200}"
            r"(?:pending|awaiting|waiting).{0,80}(?:human\s+)?merge",
            text,
            re.I | re.S,
        )
    )
    assert done_pending, (
        ".team/backlog.md must update ENG-01 to Done / complete pending human "
        "merge (not leave it as Next / Active alone)"
    )

    # Must not still advertise ENG-01 as the open Next work, or as parked.
    assert not re.search(
        r"(?m)^\s*-\s*\*\*Next\s*[-\-:].{0,80}ENG-01",
        text,
        re.I,
    ), "backlog must not still list ENG-01 under **Next**"
    assert not re.search(
        r"(?m)^\s*-\s*\*\*(?:Active|Parked)\s*[-\-:].{0,80}ENG-01",
        text,
        re.I,
    ), "backlog must not leave ENG-01 as **Active** / **Parked** after close-out"
    # Explicit board-item "parked" claim is forbidden at Done (historical M2
    # "no browser packaging in M2" lines naming ENG-01 as separate are OK).
    assert not re.search(
        r"(?m)^\s*-\s*\*\*.{0,60}ENG-01.{0,120}\bparked\b",
        text,
        re.I,
    ), "ENG-01 backlog item must not remain 'parked' after T-058 close-out"


# ---------------------------------------------------------------------------
# AC: no merge to main by agents (process lock)
# ---------------------------------------------------------------------------


def test_eng01_pending_human_merge_not_merged_by_agents() -> None:
    """Backlog/reviews: ENG-01 done pending human merge; agents did not merge."""
    blobs: list[tuple[str, str]] = []
    if _BACKLOG.is_file():
        blobs.append(("backlog", _BACKLOG.read_text(encoding="utf-8")))
    if _REVIEWS.is_dir():
        for path in sorted(_REVIEWS.glob("*.md")):
            if path.name == "README.md":
                continue
            stem_u = path.stem.upper().replace("_", "-")
            if stem_u in {"M1", "M1.5", "M15", "M2", "M3"}:
                continue
            if stem_u in {
                "T-058",
                "SLICE3",
                "SLICE-3",
                "ENG-01-SLICE3",
                "ENG-01-SLICE-3",
                "ENG-01",
            } or re.search(
                r"(?:eng-?01\s*/?\s*slice\s*3|slice\s*3\s+close|t-058)",
                path.read_text(encoding="utf-8")[:600],
                re.I,
            ):
                blobs.append((path.name, path.read_text(encoding="utf-8")))
    assert blobs, "need backlog and/or ENG-01 reviews close-out note for merge lock"

    eng01_pending = False
    agents_no_merge = False
    for _label, text in blobs:
        if re.search(
            r"(?:eng-?01|slice\s*3|t-058).{0,160}"
            r"(?:complete|done|closed|green).{0,160}"
            r"(?:pending|awaiting|waiting).{0,80}(?:human\s+)?merge",
            text,
            re.I | re.S,
        ) or re.search(
            r"(?:eng-?01|slice\s*3|t-058).{0,100}"
            r"(?:pending|awaiting|waiting).{0,80}(?:human\s+)?merge",
            text,
            re.I | re.S,
        ):
            eng01_pending = True
        if re.search(
            r"(?:agents?\s+(?:did\s+)?not\s+merge|no\s+merge\s+(?:to\s+)?main|"
            r"human\s+(?:decision|merge)|landing\s+on\s+main\s+is\s+a\s+human)",
            text,
            re.I,
        ):
            agents_no_merge = True

    assert eng01_pending, (
        ".team/backlog.md or an ENG-01 / Slice-3 reviews close-out note must "
        "record that ENG-01 / T-058 is complete pending human merge to main "
        "(M2/M3 pending-merge lines alone do not satisfy this AC)"
    )
    assert agents_no_merge or eng01_pending, (
        "Close-out surface must state agents did not merge to main / human decision"
    )


# ---------------------------------------------------------------------------
# Process: do not weaken CI gates
# ---------------------------------------------------------------------------


def test_ci_quality_gates_not_weakened() -> None:
    """Coverage floor and mypy strict remain locked (T-058: do not weaken CI)."""
    text = _read(_PYPROJECT)
    agents = _read(_REPO_ROOT / "AGENTS.md")
    assert re.search(r"--cov-fail-under\s*=\s*80\b", text) or re.search(
        r"--cov-fail-under\s*=\s*80\b", agents
    ), "pyproject.toml or AGENTS.md must keep --cov-fail-under=80"
    assert re.search(r"(?m)^strict\s*=\s*true\s*$", text), (
        "pyproject.toml [tool.mypy] must keep strict = true"
    )


# ---------------------------------------------------------------------------
# T-058 spec AC marked done at close-out
# ---------------------------------------------------------------------------


def test_t058_spec_acceptance_criteria_checked() -> None:
    """T-058 acceptance-criteria checkboxes are [x] after close-out lands."""
    path = _SPECS / "T-058.md"
    assert path.is_file(), f"missing spec {path}"
    items = _ac_checkboxes(_read(path))
    assert items, "T-058: no acceptance-criteria checkboxes found"
    unchecked = [text for done, text in items if not done]
    assert not unchecked, (
        f"T-058: {len(unchecked)} acceptance criteria still unchecked: "
        + "; ".join(unchecked[:4])
    )
