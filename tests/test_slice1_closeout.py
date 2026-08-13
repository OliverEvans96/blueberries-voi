"""T-048 Slice 1 close-out - RED / Definition-of-Done contract checks.

Asserts ENG-01 Slice-1 (T-043-T-047) process artifacts and non-goals from
``.team/specs/T-048.md`` / ``.team/plans/ENG-01-dual-runtime.md``.
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

# Slice-1 implementation tickets that must be closed for T-048 DoD.
_SLICE1_TICKETS: tuple[str, ...] = tuple(f"T-{n:03d}" for n in range(43, 48))

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

# Non-goal themes required on the Slice-1 close-out checklist surface.
_NONGOAL_THEMES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "no full WASM rewrite",
        ("wasm rewrite", "full wasm", "not a", "rewrite"),
    ),
    (
        "no matplotlib / pyarrow in browser path",
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
        ),
    ),
    (
        "API implement not required for Slice-1 DONE",
        ("api", "asgi", "slice 2", "slice-2", "http"),
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

    # Aggregated Slice-1 / ENG-01 close-out QA may mark the ticket DONE.
    for agg_name in (
        "T-048.md",
        "ENG-01-slice1.md",
        "Slice1.md",
        "slice1.md",
        "ENG-01-Slice1.md",
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
            if _RED_STATUS.search(text) and agg_name == "T-048.md":
                # T-048 RED during qa phase does not count as green for children.
                continue
            return True, f"{agg.name} lists {ticket} green/DONE"

    return False, "; ".join(details)


def _review_paths_covering(ticket: str) -> list[Path]:
    """Reviews whose subject is this ticket or Slice-1 / ENG-01 close-out."""
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
            "T-048",
            "SLICE1",
            "SLICE-1",
            "ENG-01-SLICE1",
            "ENG-01-SLICE-1",
            "ENG01-SLICE1",
            "ENG-01",
        }:
            continue
        text = path.read_text(encoding="utf-8")
        covers = bool(
            re.search(rf"\b{re.escape(ticket)}\b", text)
            or re.search(r"T-043\s*[\u2013\u2014\-]\s*T-047", text)
            or re.search(r"T-043\s+through\s+T-047", text, re.I)
            or re.search(r"Slice\s*1", text, re.I)
        )
        if covers:
            found.append(path)
    return found


def _closeout_nongoal_candidates() -> list[Path]:
    """Close-out notes expected to carry Slice-1 non-goal locks.

    Only named Slice-1 / T-048 / ENG-01 close-out files. ``.team/qa/T-048.md``
    counts only when it is no longer RED (so the qa RED map cannot satisfy the
    checklist). Historical M1.5/M2/M3 DoD notes are intentionally excluded.
    """
    names = (
        "ENG-01-slice1.md",
        "ENG-01-Slice1.md",
        "Slice1.md",
        "slice1.md",
        "T-048.md",
        "ENG-01.md",
    )
    out: list[Path] = []
    for name in names:
        for base in (_REVIEWS, _QA):
            path = base / name
            if not path.is_file():
                continue
            if base == _QA and name == "T-048.md":
                text = path.read_text(encoding="utf-8")
                if _RED_STATUS.search(text):
                    continue
            out.append(path)
    return list(dict.fromkeys(out))


def _changelog_slice1_entry() -> str | None:
    """Return the changelog block that looks like the Slice-1 / ENG-01 close-out."""
    if not _CHANGELOG.is_file():
        return None
    text = _CHANGELOG.read_text(encoding="utf-8")
    heading = re.search(
        r"^##\s+.*(Slice\s*1|ENG-01|Pyodide|browser\s+worker|interactive).*$",
        text,
        re.I | re.M,
    )
    if heading is not None:
        rest = text[heading.start() :]
        nxt = re.search(r"^##\s+", rest[3:], re.M)
        block = rest if nxt is None else rest[: nxt.start() + 3]
        # Prefer blocks that mention browser / worker / demo budget themes.
        if re.search(
            r"browser|worker|demo\s+budget|interactive|python\s+engine",
            block,
            re.I,
        ):
            return block

    bullets: list[str] = []
    for line in text.splitlines():
        if re.search(
            r"(?:Slice\s*1|browser\s+worker|demo\s+budget|interactive.{0,40}engine|"
            r"python.{0,40}browser|T-048)",
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
            r"do not|don't|asserts?\s+no|not\s+required)\b",
            window,
            re.I,
        )
    )


# ---------------------------------------------------------------------------
# AC: .team/qa/ (or ticket qa notes) records T-043-T-047 green / DONE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticket", _SLICE1_TICKETS)
def test_slice1_ticket_qa_or_verify_green(ticket: str) -> None:
    """Each Slice-1 ticket has green primary QA and/or verify PASS note."""
    ok, detail = _ticket_qa_notes_green(ticket)
    assert ok, (
        f"{ticket}: Slice-1 close-out requires green/DONE qa notes "
        f"(primary PASS or {ticket}-verify.md PASS): {detail}"
    )


@pytest.mark.parametrize("ticket", _SLICE1_TICKETS)
def test_slice1_ticket_verify_pass_artifact_present(ticket: str) -> None:
    """Each Slice-1 ticket has a verifier PASS artifact under .team/qa/."""
    path = _verify_qa(ticket)
    assert path is not None, (
        f"missing .team/qa/{ticket}-verify.md — copy from team/{ticket}/verify tip"
    )
    text = _read(path)
    assert _PASS_STATUS.search(text), (
        f"{path} must have STATUS: PASS for Slice-1 close-out"
    )
    assert not _RED_STATUS.search(text), f"{path} must not be RED/FAIL"


# ---------------------------------------------------------------------------
# AC / DoD: .team/reviews/ APPROVED for T-043-T-047
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticket", _SLICE1_TICKETS)
def test_slice1_ticket_review_approved(ticket: str) -> None:
    """Each ticket has an APPROVED review (per-ticket or Slice-1 close-out)."""
    paths = _review_paths_covering(ticket)
    assert paths, (
        f"no .team/reviews/ artifact covering {ticket} "
        f"(need STATUS: APPROVED per-ticket or Slice-1 close-out review; "
        f"copy from team/{ticket}/review)"
    )
    approved = [p for p in paths if _APPROVED.search(p.read_text(encoding="utf-8"))]
    assert approved, (
        f"reviews covering {ticket} exist but none are STATUS: APPROVED: "
        + ", ".join(p.name for p in paths)
    )


# ---------------------------------------------------------------------------
# AC: changelog plain-English Slice-1 / browser-worker entry (client voice)
# ---------------------------------------------------------------------------


def test_changelog_has_slice1_client_voice_entry() -> None:
    """Changelog: interactive Python engine runs in a browser worker under budgets."""
    assert _CHANGELOG.is_file(), f"missing {_CHANGELOG}"
    entry = _changelog_slice1_entry()
    assert entry is not None, (
        ".team/changelog.md must include a plain-English Slice-1 entry "
        "(interactive Python engine / browser worker / demo budgets; T-048)"
    )
    lowered = entry.lower()
    assert any(
        tok in lowered
        for tok in (
            "browser",
            "worker",
            "in the browser",
            "browser tab",
        )
    ), "Slice-1 changelog entry must mention the browser / worker host"
    assert any(
        tok in lowered
        for tok in (
            "python",
            "engine",
            "simulator",
            "interactive",
        )
    ), "Slice-1 changelog entry must mention the interactive Python / simulator engine"
    assert any(
        tok in lowered
        for tok in (
            "demo",
            "budget",
            "dialed",
            "small",
            "lightweight",
            "capped",
        )
    ), "Slice-1 changelog entry must mention demo / dialed budgets (not jargon-only)"
    # Client-voice: avoid a jargon-only bullet (paths / RPC / micropip alone).
    jargon_only = bool(
        re.search(r"\b(?:rpc|micropip|pyodide|asgi|wasm)\b", entry, re.I)
    ) and not any(
        tok in lowered
        for tok in (
            "you can",
            "browser",
            "run",
            "interactive",
            "demo",
        )
    )
    assert not jargon_only, (
        "Slice-1 changelog must be client-voice (what someone can do), "
        "not jargon-only (RPC/micropip/Pyodide alone)"
    )


# ---------------------------------------------------------------------------
# AC: close-out checklist asserts Slice-1 non-goals
# ---------------------------------------------------------------------------


def test_slice1_closeout_nongoals_checklist() -> None:
    """Close-out note asserts WASM / matplotlib-pyarrow / prod-N / API non-goals."""
    candidates = _closeout_nongoal_candidates()
    assert candidates, (
        "Add a Slice-1 close-out checklist under .team/reviews/ "
        "(e.g. ENG-01-slice1.md / T-048.md) asserting non-goals"
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
        # Prefer an explicit non-claim / out-of-scope nearby for each theme.
        theme_ok = False
        for tok in tokens:
            for m in re.finditer(re.escape(tok), lowered):
                if _negated_claim_window(best_text, m.start(), m.end()):
                    theme_ok = True
                    break
            if theme_ok:
                break
        if not theme_ok and re.search(
            # Checked checklist item naming the non-goal also counts.
            rf"-\s*\[[xX]\].{{0,120}}{re.escape(tokens[0])}",
            best_text,
            re.I | re.S,
        ):
            theme_ok = True
        if not theme_ok:
            missing.append(f"{label} (mentioned but not asserted as non-goal)")

    assert not missing, (
        f"{best} Slice-1 close-out missing non-goal locks: {', '.join(missing)}"
    )
    checked = len(re.findall(r"-\s*\[[xX]\]", best_text))
    assert checked > 0, (
        f"{best} must include checked [x] non-goal / DoD checklist items"
    )


# ---------------------------------------------------------------------------
# AC: plan Slice-1 waves marked complete
# ---------------------------------------------------------------------------


def test_eng01_plan_slice1_waves_complete() -> None:
    """ENG-01 plan status / Slice-1 waves marked complete at close-out."""
    text = _read(_PLAN)
    head = "\n".join(text.splitlines()[:16])
    # Ticket-map rows like "T-048 Slice-1 close-out" must NOT count as done.
    status_ok = bool(
        re.search(
            r"\*\*Status:\*\*\s*.*\b(?:COMPLETE|DONE|CLOSED|"
            r"Slice\s*1\s+(?:complete|done|closed)|"
            r"waves?\s+(?:0-4|1-4)\s+complete)\b",
            head,
            re.I,
        )
    )
    body_ok = bool(
        re.search(
            r"Slice\s*1.{0,80}(?:waves?\s+)?(?:are\s+|is\s+|marked\s+)?"
            r"(?:complete|done|closed)",
            text,
            re.I | re.S,
        )
        or re.search(
            r"(?:Wave\s*4|T-048).{0,60}(?:marked\s+)?(?:complete|done|closed)"
            r"(?!\s*-?\s*out\b)",
            text,
            re.I | re.S,
        )
        or re.search(
            r"(?:complete|done|closed).{0,60}(?:Slice\s*1|Wave\s*4)",
            text,
            re.I | re.S,
        )
    )
    assert status_ok or body_ok, (
        "`.team/plans/ENG-01-dual-runtime.md` must mark Slice-1 waves complete "
        "(status line COMPLETE/DONE or an explicit Slice 1 / Wave 4 complete note; "
        "the T-048 'close-out' ticket title alone is not enough)"
    )
    # Guard: still lists Slice 1 ticket map.
    assert re.search(r"T-048", text), "plan must still list T-048"
    assert re.search(r"Slice\s*1", text, re.I), "plan must still mention Slice 1"


# ---------------------------------------------------------------------------
# AC: no merge to main by agents (process lock)
# ---------------------------------------------------------------------------


def test_slice1_pending_human_merge_not_merged_by_agents() -> None:
    """Backlog/reviews: Slice-1 done pending human merge; agents did not merge."""
    blobs: list[tuple[str, str]] = []
    if _BACKLOG.is_file():
        blobs.append(("backlog", _BACKLOG.read_text(encoding="utf-8")))
    if _REVIEWS.is_dir():
        for path in sorted(_REVIEWS.glob("*.md")):
            if path.name == "README.md":
                continue
            stem_u = path.stem.upper().replace("_", "-")
            if stem_u in {
                "T-048",
                "SLICE1",
                "SLICE-1",
                "ENG-01-SLICE1",
                "ENG-01-SLICE-1",
                "ENG-01",
            } or re.search(r"slice\s*1", path.read_text(encoding="utf-8")[:400], re.I):
                blobs.append((path.name, path.read_text(encoding="utf-8")))
    assert blobs, "need backlog and/or Slice-1 reviews close-out note for merge lock"

    # Ignore historical M2/M3 "pending human merge" lines unless they also bind Slice-1.
    slice1_pending = False
    for label, text in blobs:
        if re.search(
            r"(?:slice\s*1|t-048).{0,120}"
            r"(?:complete|done|closed|green).{0,120}"
            r"(?:pending|awaiting|waiting).{0,80}(?:human\s+)?merge",
            text,
            re.I | re.S,
        ) or re.search(
            r"(?:slice\s*1|t-048|eng-?01\s+slice\s*1).{0,80}"
            r"(?:pending|awaiting|waiting).{0,80}(?:human\s+)?merge",
            text,
            re.I | re.S,
        ):
            slice1_pending = True
            break
        if label == "backlog" and re.search(
            r"Done\s*[\-\u2013\u2014]\s*(?:ENG-01\s+)?Slice\s*1.{0,160}"
            r"(?:pending|awaiting|waiting).{0,80}(?:human\s+)?merge",
            text,
            re.I | re.S,
        ):
            slice1_pending = True
            break

    assert slice1_pending, (
        ".team/backlog.md or a Slice-1 reviews close-out note must record that "
        "Slice-1 / T-048 is complete pending human merge to main "
        "(M2/M3 pending-merge lines alone do not satisfy this AC)"
    )


# ---------------------------------------------------------------------------
# Process: do not weaken CI gates
# ---------------------------------------------------------------------------


def test_ci_quality_gates_not_weakened() -> None:
    """Coverage floor and mypy strict remain locked (T-048: do not weaken CI)."""
    text = _read(_PYPROJECT)
    assert re.search(r"--cov-fail-under\s*=\s*80\b", text), (
        "pyproject.toml must keep --cov-fail-under=80"
    )
    assert re.search(r"(?m)^strict\s*=\s*true\s*$", text), (
        "pyproject.toml [tool.mypy] must keep strict = true"
    )


# ---------------------------------------------------------------------------
# T-048 spec AC marked done at close-out
# ---------------------------------------------------------------------------


def test_t048_spec_acceptance_criteria_checked() -> None:
    """T-048 acceptance-criteria checkboxes are [x] after close-out lands."""
    path = _SPECS / "T-048.md"
    assert path.is_file(), f"missing spec {path}"
    items = _ac_checkboxes(_read(path))
    assert items, "T-048: no acceptance-criteria checkboxes found"
    unchecked = [text for done, text in items if not done]
    assert not unchecked, (
        f"T-048: {len(unchecked)} acceptance criteria still unchecked: "
        + "; ".join(unchecked[:4])
    )
