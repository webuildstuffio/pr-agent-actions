#!/usr/bin/env python3
"""Shared decision library for jev_tag.py: schema constants, the
Layer 1 rules, the Jev job sheet + Decisions API call, and the
label decision logic. Fetched alongside jev_tag.py at the same
pinned SHA. Python 3 standard library only."""


# Re-exports (v2.2.0 module split): jev_tag.py and the tests
# import these names from jev_lib, as they did before the split.
from jev_layer1 import (SCHEMA_EFFORTS,
                        SCHEMA_PRIORITIES, SCHEMA_THEMES,
                        SCHEMA_TYPES, SEC_CATEGORIES, docs_only,
                        repo_specialties, test_gap)
from jev_layer1 import TIERS as TIERS
from jev_layer1 import layer1 as layer1
from jev_sheet import QUESTIONS as QUESTIONS
from jev_sheet import SECURITY_QUESTION_KEYS as SECURITY_QUESTION_KEYS
from jev_sheet import build_questions as build_questions
from jev_sheet import security_questions as security_questions
from jev_call import JEV_MODEL as JEV_MODEL
from jev_call import JEV_URL as JEV_URL
from jev_call import JevError as JevError
from jev_call import call_jev as call_jev
from jev_ship import L3_BUDGET_FLEET_DAY as L3_BUDGET_FLEET_DAY
from jev_ship import L3_BUDGET_REPO_DAY as L3_BUDGET_REPO_DAY
from jev_ship import REVIEW_LEVEL_NAMES as REVIEW_LEVEL_NAMES
from jev_ship import SHIP_CONFIDENTLY as SHIP_CONFIDENTLY
from jev_ship import SHIP_DEEP as SHIP_DEEP
from jev_ship import SHIP_OWNER as SHIP_OWNER
from jev_ship import SHIP_STANDARD as SHIP_STANDARD
from jev_ship import l3_budget_ok as l3_budget_ok
from jev_ship import normalize_title as normalize_title
from jev_ship import pick_wave_leader as pick_wave_leader
from jev_ship import ship_tier_and_level as ship_tier_and_level
from jev_ship import wave_dedupe_applies as wave_dedupe_applies
from jev_ship import wave_key as wave_key
from jev_state import SNIPPET_PER_FILE as SNIPPET_PER_FILE
from jev_state import SNIPPET_TOTAL_BUDGET as SNIPPET_TOTAL_BUDGET
from jev_state import STATE_BUDGET as STATE_BUDGET
from jev_state import build_security_state as build_security_state
from jev_state import build_state as build_state
from jev_state import trunc_bytes as trunc_bytes

OWNER_LABEL_MIN = 0.90        # noul needed for owner-decision / -mustdo
THEME_MIN = 0.30              # min choice probability per applied theme
TYPE_SECOND_MIN = 0.30        # min probability for a secondary type:*
EFFORT_MIN = 0.60             # min probability to apply an effort label
SEC_HIGH = 0.80               # P(security) high band
SEC_MID = 0.40                # P(security) mid band

# Step version (NOT the marker state schema, which stays jev-tag:v1).
# v2.0.0 = the combined 2026-10-28 release: the label-guard/specialty/
# new-questions iteration plus the warrant gate and the paths-only
# Layer 1 (keyword evidence deleted). Decision behavior changed
# materially, so runs across this boundary are not comparable.
# v2.0.1 = dotted compound stems (auth.service.ts) tokenize on dots
# too, restoring their Layer 1 evidence (Kody finding on PR #27).
# v2.0.2 = data-PII Layer 1 hits matched only by tech words (d1,
# migration, bare .sql) are data evidence, not security evidence:
# they no longer band high, warrant type:security or post Codex
# on their own (folio-app #3118, +8h audit 2026-10-28).
# v2.1.0 = Codex mention folded into the sticky (delimited section,
# not a separate comment); sticky uses the JEV_MENTION_PAT token.
# v2.2.0 = the top-5 improvement package (jev-plan 2026-11-06):
# (1) call_jev retries (3 attempts, ~20s timeouts, backoff) and a
# degraded run ABSTAINS (no labels beyond a Layer 1 security stamp,
# sticky flagged model-unavailable) instead of applying the
# fallback set the audit scored 0/24; (2) docs-only gate: prose
# ABOUT security cannot earn a model-route security stamp, plus
# hard-negative criteria text; (3) Layer 1 refinement: an
# infra-directory hit alone is evidence-only, and session words
# are scoped out of test paths (a third sub-rule, manifest
# version-diff, was built and dropped before release after the
# pilot replay showed collateral against warranted stamps); (4)
# escalation also posts ONE standalone `@codex security review`
# comment (the shape proven on repo-review #680 and megahealth
# #131; the in-sticky mention alone is ignored by Codex); (5)
# security questions move to a dedicated call whose state carries
# targeted patch snippets, and the Codex post requires model
# concurrence at P >= 0.40 (the security LABEL keeps its old
# rule; concurrence there was simulated net-negative).
# v2.3.0 = the recheck-v3 package (2026-11-14): (1) wave dedupe
# (G8): an escalation whose normalized title + file-path set
# matches an earlier PR in another repo within 24h that already
# posted is suppressed and noted as a wave sibling (critical
# hits always post); (2) Risk to ship: breakage_risk score +
# changes_behavior noul feed a deterministic ship tier in
# decide() (record-only: printed in the sticky, never a gate,
# never auto-merge); (3) review levels L0-L4 derived in code,
# with the @claude L3 gate input upgraded from the codex_worth
# proxy to breakage_risk; (4) test-gap Layer 1 rule plus the
# tests_cover_change noul (sticky line only); (5) sticky
# redesign: verdict line first, Codex DELIVERY state printed.
# v2.4.0 = the recheck-v5 package (2026-11-21): (1) test-gap aim:
# the flag is suppressed when Jev's own changes_behavior answer
# says no runtime behavior change (12 of v5's 21 false firings),
# Rust *_tests paths classify as tests, *.config.* basenames and
# data/ files classify as config/data instead of behavior; (2) a
# fired Codex post now also warrants the security type (the
# escalate-without-stamp divergence: torontocrimescore.com
# #437/#439/#449; replay delta 3 warranted stamps gained, 1
# stamp on an already-false post); (3) the two P4 post-route
# widenings were replay-REJECTED and are NOT here: lowering the
# Layer 1 route concurrence to 0.30 would add 13 false posts
# against 2 catches, and a P>=0.70 + blast>=3 route nets 1 catch
# against 1 known + up to 4 unknown-blast false posts (538
# judged rows, deep-dive + v3 + v5 corpora); (4) ship tier
# geometry is unchanged: replay showed every deterministic
# tightening flips more correct Deep tiers than wrong ones
# (best variant 6 fixes / 15 regressions on v5), the over-calls
# are breakage-answer noise, not geometry; the sticky verdict
# line now reads coherently for Deep + L1; (5) effort winner
# probability + margin are persisted in the marker so the P5
# abstention refit has data next time (the bar is unchanged);
# (6) miniscreen's zero-processing root cause was repo-side (its
# qodo-review workflow was manually disabled) and is fixed by
# re-enabling it, not by code here.
VERSION = "2.4.0"

# Fleet label schema v4.2 generic set (53). Anything in a repo's live
# label list NOT in this set counts as a repo specialty label.
GENERIC_LABELS = set(
    SCHEMA_PRIORITIES + ["type:" + t for t in SCHEMA_TYPES]
    + ["status:paused", "status:delayed", "status:blocked",
       "status:needs-info"] + SCHEMA_THEMES + SCHEMA_EFFORTS
    + ["needs-triage", "claude-ready", "human-only", "regression",
       "owner-decision", "owner-mustdo", "epic", "dependencies",
       "github-actions", "bun", "monthly-update", "good first issue",
       "help wanted", "invalid", "wontfix", "🤖 claude-working",
       "✅ claude-complete", "❌ claude-failed"])
SPECIALTY_MIN = 0.30          # min choice probability per specialty pick
SPECIALTY_CAP = 2             # max specialty labels applied per PR

# @claude deep-review escalation: RECORD-ONLY mode. The gate is
# scored and logged (comment footer + run record) but NO comment is
# posted: fleet claude workflows reject bot actors unless
# allowed_bots is set (separate owner-gated template change). Live
# mode must also enforce the daily budget (<=2/repo, ~6 fleet).
ESCALATION_MODE = "record-only"
ESCALATION_COMMENT = (
    "@claude please do a deep review of this pull request. "
    "Review only: post your findings as a PR review. "
    "Do not push commits and do not open pull requests.")
ESCALATION_MIN_LINES = 400    # gate: large diff by changed lines...
ESCALATION_MIN_FILES = 15     # ...or by file count

PERF_FLAG_MIN = 0.70          # P(perf risk) at/above this flags the PR
ISSUE_READY_LOW_MAX = 0.40    # P(issue ready) below this flags the issue
USER_IMPACT_MIN = 0.50        # min choice probability to act on impact
# The user-facing matcher and the comment-text builders live in
# jev_tag.py (presentation); decide() consumes the caller's
# precomputed bundle["user_facing_label"] instead.


# -------------------------------------------------------------- Decide

def top_choice(answer):
    """(winner, probability) from a choice answer, defensively."""
    if not isinstance(answer, dict):
        return None, 0.0
    probs = answer.get("probabilities") or {}
    winner = answer.get("choice")
    if winner in probs:
        return winner, float(probs[winner])
    if probs:
        winner = max(probs, key=lambda k: probs[k])
        return winner, float(probs[winner])
    return winner, 0.0


def clamp_priority(raw_idx, tier, l1, band):
    """Apply tier caps/floors. Index: 0=P0 (highest) .. 4=P4."""
    idx = raw_idx
    security = band in ("high", "mid")
    # P0 only for Layer-1-critical signals on flagship/active.
    if not (l1["critical"] and tier in ("flagship", "active")):
        idx = max(idx, 1)
    if tier == "casual":
        cap = 1 if (security and l1["any"]) or l1["critical"] else 2
        idx = max(idx, cap)
    elif tier == "dormant":
        idx = max(idx, 3 if security else 4)
    return min(max(idx, 0), 4)


def decide(bundle, l1, jev, prior=None):
    """Combine Layer 1 + Jev answers into a label decision record.

    `prior` is the step's own persisted marker state (apply mode): a
    type:security label the step itself applied earlier is in it, and
    must not be mistaken for a human security floor on re-runs."""
    answers = (jev or {}).get("answers") or {}
    tier = bundle["tier"]
    d = {
        "repo": bundle["repo"], "pr": bundle["pr_number"],
        "issue": (bundle["issue"] or {}).get("number"),
        "tier": tier, "layer1": l1,
        "jev_ok": jev is not None,
        "jev_usage": (jev or {}).get("usage"),
        "jev_model": (jev or {}).get("model"),
        "answers": answers,
    }
    # --- security band
    # A human-applied type:security on the PR or its linked issue is a
    # deterministic security floor: Jev must never downgrade it, so it
    # bands like a Layer 1 hit even when Jev is low or unavailable.
    # Labels the step itself applied (in `prior`) do not count, or a
    # mid-band self-application would self-escalate on the next run.
    def self_applied(scope):
        if not prior:
            return set()
        return set(prior.get(scope) or [])

    human_sec = (
        "type:security" in bundle["pr_labels"]
        and "type:security" not in self_applied("pr_applied"))
    if bundle["issue"] and "type:security" in bundle["issue"]["labels"]:
        same_issue = prior and prior.get("issue_number") == \
            bundle["issue"]["number"]
        if not (same_issue
                and "type:security" in self_applied("issue_applied")):
            human_sec = True
    d["human_security_label"] = human_sec
    p_sec = None
    if isinstance(answers.get("security_related"), dict):
        p_sec = answers["security_related"].get("noul")
    d["p_security_jev"] = p_sec
    blast = None
    if isinstance(answers.get("blast_radius"), dict):
        s = answers["blast_radius"].get("score")
        if isinstance(s, (int, float)):
            blast = round(float(s)) + 1  # levels 0-4 -> radius 1-5
    d["blast_radius"] = blast
    secrets_txt = None
    if isinstance(answers.get("secrets_in_text"), dict):
        secrets_txt = answers["secrets_in_text"].get("noul")
    d["p_secrets_in_text"] = secrets_txt
    l1_hard = bool(l1.get("hard"))
    d["layer1_hard"] = l1_hard
    # Security decisions key off security_hard, not any hard hit:
    # a tech-only data-PII hit (d1 / migration / .sql) is evidence
    # for Jev but must not band, warrant or post on its own
    # (folio-app #3118). Fixtures built before security_hard
    # existed fall back to hard.
    l1_sec = bool(l1.get("security_hard", l1.get("hard")))
    d["layer1_security_hard"] = l1_sec
    # v2.2.0 docs-only gate: when every changed file is prose and
    # no pasted-secret detection fires, the MODEL route alone can
    # neither band the PR nor warrant the security type nor post
    # Codex: prose ABOUT security practices, baselines, or review
    # policy is not a security change (7 of the 20 residual healthy
    # errors in the 2026-11-04 dive, one replicated docs family
    # stamped at P 0.60-0.77). Layer 1 and human warrants are
    # deterministic and unaffected.
    docs_gate = bool(docs_only(bundle)) and not l1["critical"] \
        and not (secrets_txt is not None and secrets_txt >= SEC_HIGH)
    d["docs_only_gate"] = docs_gate
    model_bands = not docs_gate
    if l1_sec or human_sec or (model_bands and p_sec is not None
                               and p_sec >= SEC_HIGH):
        band = "high"
    elif (model_bands and ((p_sec is not None and p_sec >= SEC_MID)
          or (secrets_txt is not None and secrets_txt >= SEC_HIGH))):
        band = "mid"
    elif p_sec is not None:
        band = "low"
    else:
        band = "unknown"
    d["security_band"] = band
    cat, _ = top_choice(answers.get("security_category"))
    d["security_category"] = cat if cat in SEC_CATEGORIES else None
    # The Codex post (v2.2.0): the pre-2.2.0 rule fired on ANY
    # security-hard Layer 1 hit alone, which is where the false
    # positives concentrated (healthy trigger precision 58.0%).
    # The post now requires MODEL CONCURRENCE: the (dedicated
    # security call's) P(security) at SEC_MID or more, on top of a
    # post route (Layer 1 security hit, high P, or mid P with
    # blast >= 4). A critical-filename hit (.env, key material)
    # posts without concurrence: deterministic, model-independent.
    # The human-label floor raises the band for labels, but does
    # not post on its own, and must never suppress an escalation
    # Jev earned.
    concurrence = p_sec is not None and p_sec >= SEC_MID
    d["codex_concurrence"] = bool(concurrence)
    post_route = (
        l1_sec
        or (p_sec is not None and p_sec >= SEC_HIGH)
        or (p_sec is not None and p_sec >= SEC_MID
            and blast is not None and blast >= 4))
    if docs_gate:
        # Under the docs gate only the deterministic route remains.
        post_route = l1_sec
    codex_post = bool((post_route and concurrence)
                      or l1["critical"])
    d["codex_post"] = codex_post
    # The security TYPE needs its own warrant, stricter than the
    # band. It comes from exactly two sources: (a) a Layer 1
    # SECURITY hard PATH hit (or the human-label floor), or (b)
    # Jev's own verdict with category agreement: a
    # mid-band-or-higher probability whose own security_category
    # answer is a real category, not "none". A bare mid-band
    # probability with category "none" (folio-app #3109) applied
    # type:security to a non-security PR in apply mode, and the
    # type then cascaded into the flagship priority floor. Jev's
    # secrets_in_text at high is a direct detection of pasted
    # secret material and also warrants.
    # v2.4.0 adds source (c): a fired Codex post. The post rule is
    # the stricter gate (route + concurrence, or a critical hit),
    # so a PR that earns a security review carries the type: the
    # pre-2.4.0 split escalated torontocrimescore.com #437/#439/
    # #449 (SigV4 signing and XSS fixes at P 0.43-0.82, category
    # "none") without stamping them. Replay over the combined
    # judged corpora (538 rows): 4 escalated-but-unstamped rows,
    # 3 warranted (the Toronto three), 1 not (an escalation judges
    # already scored a false post). This is NOT the concurrence-
    # on-the-label rule simulated net-negative in v2.2.0 (that one
    # REMOVED L1-only stamps); this only adds stamps where the
    # stricter post gate already fired.
    cat_agrees = cat in SEC_CATEGORIES and cat != "none"
    sec_type_warranted = (
        l1_sec or human_sec
        or (secrets_txt is not None and secrets_txt >= SEC_HIGH)
        or (not docs_gate and p_sec is not None and p_sec >= SEC_MID
            and cat_agrees)
        or codex_post)
    d["security_type_warranted"] = bool(sec_type_warranted)

    # --- types (1-3)
    types = []
    primary, primary_p = top_choice(answers.get("change_type"))
    d["type_primary"] = primary
    d["type_primary_p"] = primary_p
    if primary in SCHEMA_TYPES:
        types.append(primary)
    probs = (answers.get("change_type") or {}).get("probabilities") or {}
    for name, p in sorted(probs.items(), key=lambda kv: -kv[1]):
        if (name in SCHEMA_TYPES and name not in types
                and p >= TYPE_SECOND_MIN and len(types) < 3):
            types.append(name)
    # A change_type pick can also place "security" in types
    # directly; the warrant governs that path too, or it bypasses
    # the check.
    if "security" in types and not sec_type_warranted:
        types = [t for t in types if t != "security"]
    if (band in ("high", "mid") and sec_type_warranted
            and "security" not in types):
        if len(types) < 3:
            types.append("security")
        elif types:
            types[-1] = "security"
    # schema: a security-typed item should not also claim type:security
    # from Jev choice AND band twice; list is already deduped.
    d["types"] = types

    # --- priority (exactly 1), clamped by tier
    p_raw, p_raw_p = top_choice(answers.get("priority"))
    d["priority_jev"] = p_raw
    d["priority_jev_p"] = p_raw_p
    raw_idx = SCHEMA_PRIORITIES.index(p_raw) if p_raw in SCHEMA_PRIORITIES else 2
    idx = clamp_priority(raw_idx, tier, l1, band)
    if tier == "flagship" and any(
            t in ("bug", "security", "ci") for t in types):
        idx = min(idx, 1)  # flagship floor: P1
    if tier == "active" and any(
            t in ("bug", "security", "ci") for t in types):
        idx = min(idx, 2)  # active floor: P2 (P1 via Jev pick stands)
    d["priority"] = SCHEMA_PRIORITIES[idx]

    # --- themes (<=2 from the choice distribution)
    tprobs = (answers.get("theme") or {}).get("probabilities") or {}
    themes = [name for name, p in sorted(tprobs.items(), key=lambda kv: -kv[1]) if name in SCHEMA_THEMES and p >= THEME_MIN][:2]
    d["themes"] = themes

    # --- effort (only when confident)
    eff, eff_p = top_choice(answers.get("effort"))
    d["effort"] = eff if (eff in SCHEMA_EFFORTS and eff_p >= EFFORT_MIN) else None
    # v2.4.0: the winner's margin over the runner-up, recorded so
    # the P5 abstention refit can run on future rechecks. Recheck
    # v5 could not refit the 0.60 winner-probability bar (37.9%
    # abstention, 95.4% conditional accuracy) because NO corpus
    # records the effort distribution: the marker and the sticky
    # carried only the applied label. decide() now exposes the
    # margin and apply_decision persists both numbers in the
    # marker (additive fields). The bar itself is unchanged:
    # no distribution data, no threshold change.
    eff_probs = sorted(
        (float(p) for p in
         ((answers.get("effort") or {}).get("probabilities")
          or {}).values()
         if isinstance(p, (int, float))), reverse=True)
    # No recorded distribution (the model never answered, or the
    # answer carried no probabilities): top_choice's 0.0 is a
    # synthetic default, not a measurement. Record None so apply
    # leaves the marker field absent instead of persisting a 0.0
    # that reads as a real answer in the refit corpus (Kody, PR 64).
    d["effort_p"] = eff_p if eff_probs else None
    # No runner-up in the distribution = no measurable margin:
    # record None (the marker field stays absent) rather than the
    # winner's own probability, which would overstate confidence
    # in the refit data (Qodo, PR 64).
    d["effort_margin"] = (eff_probs[0] - eff_probs[1]
                          if len(eff_probs) > 1 else None)

    # --- owner labels (high threshold only)
    od = (answers.get("owner_decision") or {}).get("noul")
    om = (answers.get("owner_mustdo") or {}).get("noul")
    d["p_owner_decision"] = od
    d["p_owner_mustdo"] = om
    d["owner_labels"] = []
    if isinstance(od, (int, float)) and od >= OWNER_LABEL_MIN:
        d["owner_labels"].append("owner-decision")
    if isinstance(om, (int, float)) and om >= OWNER_LABEL_MIN:
        d["owner_labels"].append("owner-mustdo")

    # --- record-only signals (pilot: never acted on)
    cw = answers.get("codex_worth") or {}
    d["codex_worth_score"] = cw.get("score") if isinstance(cw, dict) else None
    lr = answers.get("low_risk") or {}
    d["p_low_risk"] = lr.get("noul") if isinstance(lr, dict) else None

    # --- Risk to ship inputs (v2.3.0): breakage_risk is a raw
    # score 0-4 (NOT blast-style +1); changes_behavior is a noul.
    br = answers.get("breakage_risk") or {}
    br_score = br.get("score") if isinstance(br, dict) else None
    if isinstance(br_score, str):
        try:
            br_score = float(br_score)
        except ValueError:
            br_score = None
    d["breakage_risk"] = (int(round(float(br_score)))
                          if isinstance(br_score, (int, float))
                          and 0 <= float(br_score) <= 4 else None)
    cb = answers.get("changes_behavior") or {}
    cb_p = cb.get("noul") if isinstance(cb, dict) else None
    d["p_changes_behavior"] = (float(cb_p)
                               if isinstance(cb_p, (int, float))
                               else None)
    # --- test gap (v2.3.0): Layer 1 fact + the middle-case noul.
    d["test_gap"] = test_gap(bundle)
    tc = answers.get("tests_cover_change") or {}
    tc_p = tc.get("noul") if isinstance(tc, dict) else None
    d["p_tests_cover_change"] = (float(tc_p)
                                 if isinstance(tc_p, (int, float))
                                 else None)
    # v2.4.0 (recheck v5, the weakest v2.3.0 line: 30/51 firings
    # correct): the flag consults Jev's own changes_behavior
    # answer. When the model itself says the PR probably does NOT
    # change runtime behavior (P < 0.50), there is no behavior to
    # test and the flag is suppressed: 12 of the 21 false firings
    # in v5 (the megamem verbatim-split series, docs/comment-only
    # and cleanup PRs) carried exactly that answer, and none of
    # the 30 correct firings did. The Layer 1 counts stay in the
    # record untouched; only the flag (and so the sticky line) is
    # gated. An unanswered changes_behavior never suppresses.
    behavior_no = (d["p_changes_behavior"] is not None
                   and d["p_changes_behavior"] < 0.50)
    d["test_gap_behavior_gate"] = bool(behavior_no and bool(
        d["test_gap"]["status"] == "hard"
        or (d["p_tests_cover_change"] is not None
            and d["p_tests_cover_change"] < 0.40)))
    d["test_gap_flag"] = bool(
        (d["test_gap"]["status"] == "hard"
         or (d["p_tests_cover_change"] is not None
             and d["p_tests_cover_change"] < 0.40))
        and not behavior_no)

    # --- specialty labels: picks come only from the repo's live
    # list (the dynamic question's criteria); outside picks, or any
    # pick when the list was never fetched, are dropped here, and
    # the apply-side guard intersects again before posting.
    specialty_picks = []
    catalog = repo_specialties(bundle.get("repo_labels"))
    if catalog:
        spec_probs = ((answers.get("specialty_labels") or {})
                      .get("probabilities") or {})
        ranked = sorted(
            ((name, float(p)) for name, p in spec_probs.items()
             if name in catalog and isinstance(p, (int, float))),
            key=lambda kv: -kv[1])
        specialty_picks = [name for name, p in ranked
                           if p >= SPECIALTY_MIN][:SPECIALTY_CAP]
    d["specialty_labels"] = specialty_picks

    # --- performance risk: high P flags the sticky comment and
    # adds the performance theme as a candidate on the issue.
    pr_perf = (answers.get("perf_risk") or {}).get("noul")
    d["p_perf_risk"] = pr_perf if isinstance(pr_perf, (int, float)) else None
    d["perf_flag"] = bool(d["p_perf_risk"] is not None
                          and d["p_perf_risk"] >= PERF_FLAG_MIN)
    d["issue_extra_labels"] = ["performance"] if d["perf_flag"] else []

    # --- linked-issue readiness: low P flags the comment + record.
    p_ready = (answers.get("issue_ready") or {}).get("noul")
    d["p_issue_ready"] = (p_ready if isinstance(p_ready, (int, float))
                          else None)
    d["issue_ready_low"] = bool(
        bundle.get("issue") and d["p_issue_ready"] is not None
        and d["p_issue_ready"] < ISSUE_READY_LOW_MAX)

    # --- user-facing impact, as a label: visible/behavior-changing
    # applies the repo's own user-facing label (live list, specialty
    # mechanism); no such label = comment line only, never invented.
    ui, ui_p = top_choice(answers.get("user_impact"))
    d["user_impact"] = (ui if ui in ("invisible", "visible",
                                     "behavior-changing")
                        and ui_p >= USER_IMPACT_MIN else None)
    d["user_impact_p"] = ui_p
    d["user_facing_label"] = None
    if d["user_impact"] in ("visible", "behavior-changing"):
        # The caller precomputed the repo's user-facing label from
        # the live list; re-intersect here so a stale or forged
        # bundle value can never invent a label.
        cand = bundle.get("user_facing_label")
        live = {lab.get("name") for lab in bundle.get("repo_labels")
                or [] if isinstance(lab, dict)}
        if cand and cand in live:
            d["user_facing_label"] = cand

    # --- affected areas (top path segments), for escalation focus
    area_counts = {}
    for f in bundle.get("files") or []:
        seg = (f.get("path") or "").split("/", 1)[0]
        if seg:
            area_counts[seg] = area_counts.get(seg, 0) + 1
    d["top_areas"] = [name for name, _ in sorted(
        area_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]

    # --- @claude deep-review escalation gate (RECORD-ONLY: scored
    # and logged, never posted; see the ESCALATION_* constants).
    files = bundle.get("files") or []
    diff_lines = sum((f.get("additions") or 0) + (f.get("deletions") or 0)
                     for f in files)
    cw_score = d["codex_worth_score"]
    # v2.3.0: the gate's risk input is breakage_risk when the
    # model answered it; the codex_worth proxy remains only as
    # the fallback for answer sets that predate the question.
    if d["breakage_risk"] is not None:
        risk_level = d["breakage_risk"]
        esc_risk_ok = bool(
            risk_level >= 3
            or (risk_level == 2 and blast is not None and blast >= 4))
    else:
        risk_level = (int(round(float(cw_score)))
                      if isinstance(cw_score, (int, float)) else None)
        esc_risk_ok = bool(
            risk_level is not None
            and (risk_level >= 4 or (risk_level == 3 and blast == 5)))
    esc_size_ok = bool(diff_lines >= ESCALATION_MIN_LINES
                       or len(files) >= ESCALATION_MIN_FILES)
    esc_tier_ok = tier in ("flagship", "active")
    esc_prior_ok = not (prior and prior.get("escalation_noted"))
    escalation = {
        "mode": ESCALATION_MODE,
        "would_fire": bool(esc_risk_ok and esc_size_ok and esc_tier_ok
                           and esc_prior_ok),
        "risk_ok": esc_risk_ok, "size_ok": esc_size_ok,
        "tier_ok": esc_tier_ok, "prior_ok": esc_prior_ok,
        "risk_level": risk_level, "diff_lines": diff_lines,
        "files_changed": len(files),
        "budget": ("record-only: nothing is posted, no budget is "
                   "consumed; live mode must enforce <=2 per repo "
                   "per day, ~6 fleet-wide (l3_budget_ok)"),
        "comment": None,
    }
    # The caller builds escalation["comment"] when the gate fires.
    d["escalation"] = escalation

    # --- Ship tier + review level (v2.3.0, RECORD-ONLY: printed
    # in the sticky and stored in the marker/record; drives no
    # merge behaviour, Jev still never gates a merge). The tier
    # geometry itself lives in jev_ship.ship_tier_and_level.
    brk = d["breakage_risk"]
    deep_risk = bool(brk is not None and brk == 2
                     and blast is not None and blast >= 4)
    ship_tier, level = ship_tier_and_level(
        brk, d["p_changes_behavior"], band, bool(l1["critical"]),
        d["owner_labels"], bool(sec_type_warranted), codex_post,
        escalation["would_fire"], deep_risk=deep_risk)
    d["ship_tier"] = ship_tier
    d["review_level"] = level
    d["review_level_name"] = REVIEW_LEVEL_NAMES[level]

    desired = [d["priority"]] + [f"type:{t}" for t in types] + themes + d["owner_labels"]
    if d["effort"]:
        desired.append(d["effort"])
    desired.extend(specialty_picks)
    if d["user_facing_label"]:
        desired.append(d["user_facing_label"])
    # v2.2.0 ABSTAIN: when the model call failed (jev is None, after
    # retries), the run applies NOTHING beyond a Layer 1 security
    # stamp. The pre-2.2.0 degraded path applied a manufactured set
    # (tier-clamped default priority plus the stamp) that the audit
    # scored wrong 24 of 24. The full decision stays in the record
    # for diagnosis; only the applied set is gated, and the sticky
    # flags the run as model-unavailable.
    d["abstained"] = jev is None
    if d["abstained"]:
        desired = [x for x in desired if x == "type:security"]
    d["labels_desired"] = desired
    return d


def plan_labels(desired, existing, vetoed):
    """Labels to ADD for one target: additive only, schema caps and
    the human-veto set respected, never a second priority."""
    have = set(existing)
    adds = []

    def room(kind, cap):
        return sum(1 for lab in have if kind(lab)) < cap

    for label in desired:
        if label in have or label in vetoed:
            continue
        if label in SCHEMA_PRIORITIES:
            if any(lab in SCHEMA_PRIORITIES for lab in have):
                continue
        elif label.startswith("type:"):
            if not room(lambda lab: lab.startswith("type:"), 3):
                continue
        elif label in SCHEMA_THEMES:
            if not room(lambda lab: lab in SCHEMA_THEMES, 2):
                continue
        elif label.startswith("effort:"):
            if any(lab.startswith("effort:") for lab in have):
                continue
        adds.append(label)
        have.add(label)
    return adds
