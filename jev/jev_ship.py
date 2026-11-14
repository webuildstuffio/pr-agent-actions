#!/usr/bin/env python3
"""Ship tier, review levels, and wave dedupe for jev_tag.py
(v2.3.0). Split out of jev_lib.py at creation (file-length
limit); jev_lib re-exports everything here. Pure functions
only: no I/O, so the tier geometry and the wave grouping are
unit-testable offline. Python 3 standard library only."""

import re
from datetime import datetime, timezone


# Ship tiers (v2.3.0, record-only: printed in the sticky and
# stored in the marker/record; drives no merge behaviour).
SHIP_CONFIDENTLY = "Ship confidently"
SHIP_STANDARD = "Ship after standard review"
SHIP_DEEP = "Deep review required"
SHIP_OWNER = "Owner must look"
REVIEW_LEVEL_NAMES = {
    0: "L0 (Qodo only)",
    1: "L1 (Codex general)",
    2: "L2 (Codex security)",
    3: "L3 (Claude deep review, record-only)",
    4: "L4 (Owner eyes)",
}
# L3 daily budget (record-only today: nothing is posted, so no
# budget is consumed; these are the limits live mode must
# enforce, kept as constants the counting helper is tested
# against).
L3_BUDGET_REPO_DAY = 2
L3_BUDGET_FLEET_DAY = 6


def l3_budget_ok(repo_today, fleet_today):
    """True when one more L3 post fits the daily budget."""
    return (repo_today < L3_BUDGET_REPO_DAY
            and fleet_today < L3_BUDGET_FLEET_DAY)


def ship_tier_and_level(brk, p_changes_behavior, band, critical,
                        owner_labels, sec_type_warranted, codex_post,
                        escalation_would_fire, deep_risk=False):
    """(ship_tier, review_level) from the decide() inputs.

    Owner must look: an owner label applied, a Layer 1 critical
    hit, or breakage 4 on a high band. Deep review required:
    breakage >= 3, breakage 2 with the caller-resolved deep
    condition, or a Codex post. Ship confidently: breakage 0,
    behavior probably unchanged, low band, no critical. Every
    other case, including answer sets with no breakage score,
    is Ship after standard review: that is today's default for
    every PR, so the fallback cannot under-review anything."""
    owner_look = bool(owner_labels or critical
                      or (brk == 4 and band == "high"))
    deep = bool(codex_post or deep_risk
                or (brk is not None and brk >= 3))
    if owner_look:
        tier = SHIP_OWNER
    elif deep:
        tier = SHIP_DEEP
    elif (brk == 0 and p_changes_behavior is not None
            and p_changes_behavior < 0.40 and band == "low"
            and not critical):
        tier = SHIP_CONFIDENTLY
    else:
        tier = SHIP_STANDARD
    level = 1
    if tier == SHIP_CONFIDENTLY and not sec_type_warranted:
        level = 0
    if codex_post:
        level = max(level, 2)
    if escalation_would_fire:
        level = max(level, 3)
    if owner_look:
        level = 4
    return tier, level


# ---------------------------------------------------------- Wave dedupe

def normalize_title(title):
    """Wave-family title key: case/punctuation-insensitive."""
    return re.sub(r"\s+", " ", re.sub(
        r"[^a-z0-9]+", " ", (title or "").lower())).strip()


def wave_key(title, paths):
    return (normalize_title(title), tuple(sorted(paths or [])))


def _parse_ts(text):
    if not text:
        return None
    try:
        return datetime.fromisoformat(
            str(text).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def pick_wave_leader(candidates, self_ref, title, paths,
                     created_at, window_hours=24):
    """The earliest already-posted wave sibling, or None.

    `candidates` are plain dicts {repo, number, title, paths,
    created_at, posted}. A sibling must share the wave key
    (normalized title + identical file-path set), be in a
    DIFFERENT repo (a wave is a cross-repo family; a same-repo
    twin is a duplicate PR, not a wave sibling), have been
    created earlier (ties break on repo/number so the leader is
    deterministic), sit inside the window, and have actually
    posted its standalone Codex comment: a sibling that never
    escalated is not a leader, this PR is."""
    key = wave_key(title, paths)
    self_time = _parse_ts(created_at)
    if self_time is None:
        return None
    best = None
    for c in candidates or []:
        ref = (c.get("repo"), c.get("number"))
        if ref == self_ref or ref[0] == self_ref[0] \
                or not c.get("posted"):
            continue
        if wave_key(c.get("title"), c.get("paths")) != key:
            continue
        t = _parse_ts(c.get("created_at"))
        if t is None:
            continue
        delta = (self_time - t).total_seconds()
        if delta < 0 or delta > window_hours * 3600:
            continue
        if delta == 0 and ref >= self_ref:
            continue
        rank = (t, str(ref[0]), ref[1] or 0)
        if best is None or rank < best[0]:
            best = (rank, {"repo": c.get("repo"),
                           "number": c.get("number")})
    return best[1] if best else None


def wave_dedupe_applies(d, l1):
    """Dedupe may suppress a post only when the post rule fired
    and no Layer 1 critical hit exists: critical hits always
    post, dedupe or not."""
    return bool(d.get("codex_post") and not (l1 or {}).get("critical"))
