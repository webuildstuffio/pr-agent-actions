#!/usr/bin/env python3
"""Presentation for jev_tag.py: the sticky comment body, the
Codex trigger renderings, and the user-facing label matcher.
Split out of jev_tag.py in v2.2.0 (file-length limit); jev_tag
re-exports everything here. Python 3 standard library only."""

import json
import re

from jev_lib import ESCALATION_COMMENT, GENERIC_LABELS, VERSION


BAND_DOTS = {"high": "🔴", "mid": "🟡", "low": "🟢"}


TIER_DOTS = {"Ship confidently": "🟢",
             "Ship after standard review": "🟢",
             "Deep review required": "🔴",
             "Owner must look": "🔴"}


def marker_body(state, d, adds_pr, adds_issue, codex_now,
                issue_number=None, skipped=None, escalated=False,
                codex_identity=None, codex_state=None):
    """The sticky status comment (v2.3.0 redesign): verdict line
    first (ship tier + review level), then labels, security with
    the Codex DELIVERY state, risk, and conditional lines only
    when they fire. The machine state stays hidden in the
    HTML-comment marker; nothing raw is rendered."""
    band = d.get("security_band") or "unknown"
    lines = []
    if d.get("abstained"):
        lines.append("⚪ **Jev: no verdict · model unavailable**")
    elif d.get("ship_tier"):
        lvl = d.get("review_level_name") or ""
        # v2.4.0 verdict-line coherence (recheck v4/v5 finding):
        # "Deep review required · L1 (Codex general)" reads as a
        # contradiction, because the tier can rise on breakage
        # alone while the level only rises on a Codex post, the
        # L3 gate, or an owner condition (24 of 62 Deep tiers in
        # v5 sat at L1). The numeric level stays what it is; the
        # line now says where the deep review comes from.
        if d["ship_tier"] == "Deep review required" \
                and d.get("review_level") == 1:
            lvl += " + human deep review"
        lines.append(
            f"{TIER_DOTS.get(d['ship_tier'], '⚪')} **Jev: "
            f"{d['ship_tier']} · Review level {lvl}**")
    else:
        lines.append(f"{BAND_DOTS.get(band, '⚪')} **Jev tagging**")
    if adds_pr:
        lines.append("**Labels:** "
                     + ", ".join(f"`{x}`" for x in adds_pr))
    else:
        lines.append("**Labels:** no changes")
    if issue_number:
        if adds_issue:
            lines.append(f"**Issue #{issue_number} labels:** "
                         + ", ".join(f"`{x}`" for x in adds_issue))
        else:
            lines.append(f"**Issue #{issue_number} labels:** no changes")
    else:
        lines.append("🔗 No linked issue found, so labels were "
                     "applied to the PR only")
    p = d.get("p_security_jev")
    ptxt = f"{p:.2f}" if isinstance(p, (int, float)) else "n/a"
    blast = d.get("blast_radius")
    sec = (f"🔒 Security: band **{band}** · P {ptxt} · "
           f"blast {blast if blast is not None else '—'}")
    cat = d.get("security_category")
    if cat and cat != "none":
        sec += f" · area: {cat}"
    l1 = d.get("layer1") or {}
    if l1.get("any"):
        hits = ", ".join(_code_span(h["match"])
                         for h in l1["hits"][:2])
        sec += f" · rule hits: {hits}"
    if not codex_now and not d.get("codex_posted_before") \
            and not d.get("codex_post") \
            and not d.get("wave_sibling"):
        sec += " · no security review needed"
    lines.append(sec)
    # Codex DELIVERY state (v2.3.0): "requested" was a lie on
    # non-PAT repos, where a bot-authored standalone comment
    # triggers nothing (0 of 40 delivered in the v3 recheck).
    # Say who posted it and what that means.
    if codex_now or d.get("codex_posted_before") or escalated:
        if codex_state:
            safe = str(codex_state).replace("`", "'") \
                .replace("\n", " ")[:40]
            delivery = f"state: **{safe}**"
        elif codex_identity and codex_identity != "github-actions[bot]":
            delivery = "state: posted, awaiting Codex"
        elif codex_identity == "github-actions[bot]" or codex_now:
            delivery = ("state: **not delivered (bot mentions do "
                        "not trigger Codex; PAT does not reach "
                        "this repo)** · escalation is record-only "
                        "here")
        else:
            delivery = "state: posted earlier"
        who = (f"posted as {_code_span(str(codex_identity))}"
               if codex_identity else "posted earlier")
        lines.append(f"🛡️ Codex security review: standalone "
                     f"comment {who} · {delivery}")
    if d.get("wave_sibling"):
        sib = d["wave_sibling"]
        lines.append(
            "🌊 Wave sibling of "
            + _code_span(f"{sib.get('repo')}#{sib.get('number')}")
            + ": escalation posted there, not repeated here")
    if d.get("abstained"):
        lines.append("⚠️ **Model unavailable:** Jev did not answer "
                     "after retries, so this run abstained. Labels "
                     "are incomplete: only deterministic Layer 1 "
                     "stamps were applied, if any.")
    # Risk line: printed whenever the new answers exist.
    if d.get("breakage_risk") is not None \
            or d.get("p_changes_behavior") is not None:
        risk = f"⚠️ Risk to ship: breakage {d.get('breakage_risk')}/4"
        cb = d.get("p_changes_behavior")
        risk += (" · behavior-changing: "
                 + ("yes" if cb is not None and cb >= 0.50
                    else "no" if cb is not None else "—"))
        pp = d.get("p_perf_risk")
        risk += (" · perf risk: "
                 + ("yes" if d.get("perf_flag") else "no"
                    if pp is not None else "—"))
        lines.append(risk)
    if d.get("test_gap_flag"):
        gap = d.get("test_gap") or {}
        if gap.get("status") == "hard":
            lines.append("🧪 Tests: no test files touched on a "
                         "behavior change")
        else:
            tp = d.get("p_tests_cover_change")
            lines.append(f"🧪 Tests: test changes may not exercise "
                         f"the changed behavior (P {tp:.2f})")
    if escalated:
        # Body rebuilt from scratch per render: exactly one section.
        lines.extend(escalation_section(d))
    themes = d.get("themes") or []
    eff = d.get("effort")
    lines.append("🏷️ Themes: "
                 + (", ".join(themes) if themes else "—")
                 + f" · Effort: {eff or '—'}")
    if d.get("perf_flag"):
        pp = d.get("p_perf_risk")
        lines.append(f"⚡ Perf risk flagged (P {pp:.2f}): possible "
                     "speed impact, worth a second look")
    if d.get("issue_ready_low"):
        rp = d.get("p_issue_ready")
        lines.append(f"🧩 Linked issue may be underspecified "
                     f"(readiness P {rp:.2f})")
    if d.get("user_impact") in ("visible", "behavior-changing"):
        ui_line = f"👀 User impact: **{d['user_impact']}**"
        if d.get("user_facing_label"):
            ui_line += f" · label `{d['user_facing_label']}` applied"
        else:
            ui_line += " · no user-facing label in this repo"
        lines.append(ui_line)
    notes = list(skipped or [])
    esc = d.get("escalation") or {}
    if esc.get("would_fire"):
        # Deliberately NOT phrased as a mention: the note itself must
        # never trigger the workflow it describes.
        notes.append("deep-review escalation would fire "
                     "(record-only, not posted)")
    if notes:
        shown = notes[:4]
        if len(notes) > 4:
            shown.append(f"+{len(notes) - 4} more")
        lines.append("<sub>Skipped/notes: " + "; ".join(shown)
                     + "</sub>")
    lines.append(f"<sub>jev-tag v{VERSION} · one Jev pass at "
                 "open; CI and reviewer findings are not in "
                 "this verdict</sub>")
    payload = json.dumps(state, separators=(",", ":"), sort_keys=True)
    return f"<!-- jev-tag:v1 {payload} -->\n" + "\n".join(lines)


# ------------------------------------------------------- Presentation

# Deterministic matcher for a repo's user-facing label (must exist in
# the live list; never invented). Names match the full pattern;
# descriptions match only explicit phrases, so a stray "UI" in an
# area label's description cannot hijack the pick.
USER_FACING_NAME_RE = re.compile(
    r"user[- ]?facing|customer[- ]?facing|end[- ]?user|front[- ]?end"
    r"|\bux\b|\bui\b", re.IGNORECASE)
USER_FACING_DESC_RE = re.compile(
    r"user[- ]?facing|customer[- ]?facing|end[- ]?user", re.IGNORECASE)


def match_user_facing_label(repo_labels):
    """The repo's user-facing label name from its live label list, or
    None. Specialty (non-generic) labels win over generic ones; ties
    break alphabetically so the pick is deterministic."""
    if not isinstance(repo_labels, list):
        return None
    matches = []
    for item in repo_labels:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or ""
        desc = item.get("description") or ""
        if name and (USER_FACING_NAME_RE.search(name)
                     or USER_FACING_DESC_RE.search(desc)):
            matches.append(name)
    if not matches:
        return None
    matches.sort(key=lambda n: (n in GENERIC_LABELS, n))
    return matches[0]


def _code_span(text):
    """Render an author-controlled string (a file path or area name)
    as an inline code span in a bot-posted comment: code spans
    suppress @mentions and markdown, so a crafted path cannot fire
    a mention or inject markup (Kody security finding on PR 26).
    Backticks and newlines inside the value are neutralized so the
    span cannot be broken out of."""
    return "`" + text.replace("`", "'").replace("\r", " ") \
        .replace("\n", " ") + "`"


def codex_focus(d):
    """Codex trigger comment body: the exact trigger string verbatim
    on line 1 (so the mention parses as the review request, not a
    free-form task), then Jev's specific concerns in the SAME comment
    (owner correction 2026-10-28: less auto, more specific).

    Since v2.1.0 the trigger ships via escalation_section() inside
    the sticky; this stays as the reference rendering for it."""
    lines = ["@codex security review", "",
             "Jev context for this review:"]
    band = d.get("security_band") or "unknown"
    p = d.get("p_security_jev")
    ptxt = f"{p:.2f}" if isinstance(p, (int, float)) else "n/a"
    sec = f"- Security: band {band}, P {ptxt}"
    blast = d.get("blast_radius")
    if blast is not None:
        sec += f", blast radius {blast} of 5"
    cat = d.get("security_category")
    if cat and cat != "none":
        sec += f", area: {cat}"
    lines.append(sec)
    files = []
    for h in (d.get("layer1") or {}).get("hits") or []:
        if h.get("kind") == "path" and h.get("match") not in files:
            files.append(h["match"])
    if files:
        lines.append("- Files of concern: "
                     + ", ".join(_code_span(f) for f in files[:5]))
    elif d.get("top_areas"):
        lines.append("- Areas of concern: "
                     + ", ".join(_code_span(a)
                                 for a in d["top_areas"]))
    if d.get("perf_flag"):
        lines.append("- Performance risk also flagged by Jev")
    return "\n".join(lines)


def escalation_section(d):
    """The Codex escalation block inside the sticky (v2.1.0, owner
    call 2026-10-28): the trigger rides in the sticky instead of a
    separate bot comment Codex ignores. The trigger string is an
    exact line of its own; EVERY interpolated value is code-span
    escaped (the PR #26 rule, all values), so no author-controlled
    string can fire a mention or break out of its span."""
    lines = ["---", "🔐 **Codex security review**", "",
             "@codex security review", "", "Jev context for this review:"]
    band = d.get("security_band") or "unknown"
    p = d.get("p_security_jev")
    ptxt = f"{p:.2f}" if isinstance(p, (int, float)) else "n/a"
    sec = f"- Security: band {_code_span(str(band))}, P {ptxt}"
    blast = d.get("blast_radius")
    if isinstance(blast, (int, float)):
        sec += f", blast radius {blast} of 5"
    elif blast is not None:
        sec += f", blast radius {_code_span(str(blast))}"
    cat = d.get("security_category")
    if cat and cat != "none":
        sec += f", area: {_code_span(str(cat))}"
    lines.append(sec)
    files = []
    for h in (d.get("layer1") or {}).get("hits") or []:
        if h.get("kind") == "path" and h.get("match") not in files:
            files.append(h["match"])
    if files:
        lines.append("- Files of concern: "
                     + ", ".join(_code_span(str(f))
                                 for f in files[:5]))
    elif d.get("top_areas"):
        lines.append("- Areas of concern: "
                     + ", ".join(_code_span(str(a))
                                 for a in d["top_areas"]))
    if d.get("perf_flag"):
        lines.append("- Performance risk also flagged by Jev")
    return lines


def escalation_comment(d):
    """The would-be deep-review comment text (record-only mode: built
    and logged, never posted). Review-only instruction first, then
    Jev's specific concerns as the reviewer's focus list."""
    concerns = []
    cat = d.get("security_category")
    if cat and cat != "none":
        concerns.append(f"security area: {cat}")
    if d.get("perf_flag"):
        concerns.append("performance risk flagged by Jev")
    if d.get("blast_radius") is not None:
        concerns.append(f"blast radius {d['blast_radius']} of 5")
    if d.get("top_areas"):
        concerns.append("affected areas: "
                        + ", ".join(_code_span(a)
                                    for a in d["top_areas"]))
    if d.get("themes"):
        concerns.append("themes: " + ", ".join(d["themes"]))
    focus = (" Focus on: " + "; ".join(concerns) + "."
             if concerns else "")
    return ESCALATION_COMMENT + focus
