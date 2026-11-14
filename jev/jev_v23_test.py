#!/usr/bin/env python3
"""Offline self-test for the Jev v2.3.0 package (wave dedupe,
Risk to ship tiers, review levels, test gap, sticky verdict
cases). Split out of jev_tag_test.py at creation (file-length
limit). Run: python3 jev_v23_test.py, exits non-zero on FAIL."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jev_lib import (build_questions, decide, l3_budget_ok,
                     normalize_title, pick_wave_leader, test_gap,
                     wave_dedupe_applies, wave_key)
from jev_tag import (codex_security_state, marker_body,
                     standalone_delivered, trigger_author)


def v23_tests():
    """v2.3.0: wave dedupe, Risk to ship tiers, review levels,
    test gap, sticky verdict cases."""
    ok = True

    def check(name, cond):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name)
        ok = ok and bool(cond)

    plain = {"hits": [], "any": False, "critical": False,
             "categories": [], "hard": False, "security_hard": False}
    crit = dict(plain, critical=True, any=True)

    def mk_bundle(**over):
        b = {"repo": "webuildstuffio/x", "pr_number": 3,
             "pr_title": "t", "pr_body": "", "pr_author": "a",
             "pr_labels": [], "files": [], "issue": None,
             "tier": "flagship", "readme": "", "agents": "",
             "repo_labels": None}
        b.update(over)
        return b

    def mk_answers(**over):
        a = {"security_related": {"type": "noul", "noul": 0.1},
             "security_category": {"type": "choice", "choice": "none",
                                   "probabilities": {"none": 0.9}},
             "blast_radius": {"type": "score", "score": 1.0},
             "change_type": {"type": "choice", "choice": "feature",
                             "probabilities": {"feature": 0.9}},
             "priority": {"type": "choice", "choice": "P2",
                          "probabilities": {"P2": 0.8}},
             "codex_worth": {"type": "score", "score": 1.0}}
        a.update(over)
        return {"answers": a}

    def ans(br=None, cb=None, **over):
        if br is not None:
            over["breakage_risk"] = {"type": "score", "score": float(br)}
        if cb is not None:
            over["changes_behavior"] = {"type": "noul", "noul": cb}
        return mk_answers(**over)

    # --- wave dedupe grouping
    check("wave title normalize",
          normalize_title("Qodo v3.9.3: Repin!") == "qodo v3 9 3 repin")
    check("wave key sorts paths",
          wave_key("T", ["b.ts", "a.ts"]) == wave_key("t", ["a.ts", "b.ts"]))
    self_ref = ("webuildstuffio/x", 5)
    cand = [{"repo": "webuildstuffio/y", "number": 9,
             "title": "Sync Thing!", "paths": ["a.ts"],
             "created_at": "2026-11-14T10:00:00Z", "posted": True}]
    check("wave leader found",
          pick_wave_leader(cand, self_ref, "sync thing", ["a.ts"],
                           "2026-11-14T12:00:00Z")
          == {"repo": "webuildstuffio/y", "number": 9})
    check("wave leader needs identical paths",
          pick_wave_leader(cand, self_ref, "sync thing", ["b.ts"],
                           "2026-11-14T12:00:00Z") is None)
    check("wave leader needs posted sibling",
          pick_wave_leader([dict(cand[0], posted=False)], self_ref,
                           "sync thing", ["a.ts"],
                           "2026-11-14T12:00:00Z") is None)
    check("wave leader window 24h",
          pick_wave_leader(cand, self_ref, "sync thing", ["a.ts"],
                           "2026-11-15T12:00:01Z") is None)
    check("wave leader not self / not later",
          pick_wave_leader(cand, ("webuildstuffio/y", 9), "sync thing",
                           ["a.ts"], "2026-11-14T09:00:00Z") is None)
    check("wave leader excludes same repo",
          pick_wave_leader(
              [dict(cand[0], repo="webuildstuffio/x", number=9)],
              self_ref, "sync thing", ["a.ts"],
              "2026-11-14T12:00:00Z") is None)
    check("breakage score coerces numeric strings",
          decide(mk_bundle(), plain, mk_answers(
              breakage_risk={"type": "score", "score": "3"},
              changes_behavior={"type": "noul", "noul": 0.9}))
          ["breakage_risk"] == 3)
    check("codex state ignores forged author",
          codex_security_state([{
              "user": {"login": "mallory"},
              "body": ('<!-- codex-review-state:v1 '
                       '{"security_review": {"status": '
                       '"completed"}} -->')}]) is None)
    st_posted = {"codex_posted": True,
                 "codex_standalone_posted": True}
    check("standalone delivered needs human author",
          standalone_delivered(
              [{"user": {"login": "nichm"},
                "body": "@codex security review"}], st_posted) is True
          and standalone_delivered(
              [{"user": {"login": "github-actions[bot]"},
                "body": "@codex security review"}], st_posted) is False
          and standalone_delivered(
              [{"user": {"login": "nichm"},
                "body": "@codex security review"}], {}) is False)
    check("trigger author from the existing comment",
          trigger_author([{"user": {"login": "nichm"},
                           "body": "@codex security review"}])
          == "nichm"
          and trigger_author([{"user": {"login": "nichm"},
                               "body": "unrelated"}]) is None)
    check("codex state parses nested object",
          codex_security_state([{
              "user": {"login": "chatgpt-codex-connector[bot]"},
              "body": ('<!-- codex-review-state:v1 '
                       '{"security_review": {"status": '
                       '"completed"}} -->')}]) == "completed")
    check("wave dedupe never on critical",
          wave_dedupe_applies({"codex_post": True}, crit) is False
          and wave_dedupe_applies({"codex_post": True}, plain) is True
          and wave_dedupe_applies({"codex_post": False}, plain) is False)

    # --- ship tier boundaries
    d = decide(mk_bundle(), plain, ans(br=0, cb=0.2))
    check("tier confidently",
          d["ship_tier"] == "Ship confidently" and d["review_level"] == 0)
    d = decide(mk_bundle(), plain, ans(br=0, cb=0.9))
    check("tier standard when behavior changes",
          d["ship_tier"] == "Ship after standard review"
          and d["review_level"] == 1)
    d = decide(mk_bundle(), plain, ans(br=1, cb=0.9))
    check("tier standard at breakage 1",
          d["ship_tier"] == "Ship after standard review")
    d = decide(mk_bundle(), plain, ans(br=2, cb=0.9))
    check("tier standard at breakage 2 low blast",
          d["ship_tier"] == "Ship after standard review")
    d = decide(mk_bundle(), plain, ans(
        br=2, cb=0.9, blast_radius={"type": "score", "score": 3.4}))
    check("tier deep at breakage 2 blast 4",
          d["ship_tier"] == "Deep review required")
    d = decide(mk_bundle(), plain, ans(br=3, cb=0.9))
    check("tier deep at breakage 3",
          d["ship_tier"] == "Deep review required")
    d = decide(mk_bundle(), plain, ans(
        br=4, cb=0.9, security_related={"type": "noul", "noul": 0.9},
        security_category={"type": "choice", "choice": "auth",
                           "probabilities": {"auth": 0.9}}))
    check("tier owner at breakage 4 high band",
          d["ship_tier"] == "Owner must look" and d["review_level"] == 4)
    d = decide(mk_bundle(), plain, ans(
        br=0, cb=0.1, owner_mustdo={"type": "noul", "noul": 0.95}))
    check("tier owner on owner_mustdo",
          d["ship_tier"] == "Owner must look" and d["review_level"] == 4)
    d = decide(mk_bundle(), crit, ans(br=0, cb=0.1))
    check("tier owner on critical hit",
          d["ship_tier"] == "Owner must look" and d["review_level"] == 4)
    d = decide(mk_bundle(), plain, ans(
        br=0, cb=0.1, security_related={"type": "noul", "noul": 0.9},
        security_category={"type": "choice", "choice": "auth",
                           "probabilities": {"auth": 0.9}}))
    check("tier deep + L2 when codex posts",
          d["ship_tier"] == "Deep review required"
          and d["review_level"] == 2 and d["codex_post"] is True)
    # L3: breakage-driven gate on a big flagship diff
    big = [{"path": "src/a.ts", "additions": 300, "deletions": 150}]
    d = decide(mk_bundle(files=big), plain, ans(br=3, cb=0.9))
    check("L3 gate fires on breakage 3 big diff",
          d["escalation"]["would_fire"] is True
          and d["review_level"] == 3)
    check("L3 budget helper",
          l3_budget_ok(1, 5) is True and l3_budget_ok(2, 3) is False
          and l3_budget_ok(0, 6) is False)
    check("no literal mention string in level names",
          "@claude" not in d["review_level_name"])

    # --- test gap
    src = [{"path": "src/a.ts", "additions": 5, "deletions": 0}]
    tst = [{"path": "src/a.test.ts", "additions": 5, "deletions": 0}]
    check("test gap hard",
          test_gap({"files": src})["status"] == "hard")
    check("test gap none when tests moved",
          test_gap({"files": src + tst})["status"] is None)
    check("test gap config-only allowlisted",
          test_gap({"files": [{"path": "wrangler.toml",
                               "additions": 1, "deletions": 0}]})["status"]
          is None)
    check("test gap lockfile allowlisted",
          test_gap({"files": [{"path": "bun.lock",
                               "additions": 1, "deletions": 0}]})["status"]
          is None)
    check("test gap migrations-only allowlisted",
          test_gap({"files": [{"path": "migrations/0001.sql",
                               "additions": 1, "deletions": 0}]})["status"]
          is None)
    check("test gap generated allowlisted",
          test_gap({"files": [{"path": "src/gen/api.generated.ts",
                               "additions": 1, "deletions": 0}]})["status"]
          is None)
    check("tests_cover question only when both moved",
          "tests_cover_change" in build_questions(mk_bundle(files=src + tst))
          and "tests_cover_change" not in build_questions(
              mk_bundle(files=src)))
    d = decide(mk_bundle(files=src), plain, ans(br=1, cb=0.9))
    check("decide carries hard test gap",
          d["test_gap_flag"] is True and d["test_gap"]["status"] == "hard")
    d = decide(mk_bundle(files=src + tst), plain, ans(
        br=1, cb=0.9,
        tests_cover_change={"type": "noul", "noul": 0.2}))
    check("decide flags weak test coverage noul",
          d["test_gap_flag"] is True and d["test_gap"]["status"] is None)

    # --- sticky rendering, 4 cases
    state = {"pr_applied": [], "issue_applied": [],
             "issue_number": None, "codex_posted": False, "runs": 1}
    d = decide(mk_bundle(files=src), plain, ans(br=1, cb=0.9))
    body = marker_body(state, d, ["P2", "type:feature"], [], False)
    check("sticky normal verdict first",
          "**Jev: Ship after standard review · Review level "
          "L1 (Codex general)**" in body
          and "Risk to ship: breakage 1/4" in body
          and "🧪 Tests: no test files touched" in body
          and "no security review needed" in body)
    d_sec = decide(mk_bundle(), plain, ans(
        br=2, cb=0.5, security_related={"type": "noul", "noul": 0.93},
        security_category={"type": "choice", "choice": "auth",
                           "probabilities": {"auth": 0.9}}))
    body = marker_body(state, d_sec, ["P1"], [], True,
                       codex_identity="nichm")
    check("sticky PAT escalated delivery",
          "posted as `nichm`" in body and "not delivered" not in body)
    body = marker_body(state, d_sec, ["P1"], [], True,
                       codex_identity="github-actions[bot]")
    check("sticky non-PAT escalated honesty line",
          "not delivered (bot mentions do not trigger Codex; "
          "PAT does not reach this repo)" in body)
    d_before = dict(d_sec, codex_posted_before=True)
    body = marker_body(state, d_before, ["P1"], [], False,
                       codex_identity="nichm")
    check("sticky earlier human trigger not mislabeled bot",
          "posted as `nichm`" in body and "not delivered" not in body)
    body = marker_body(state, d_before, ["P1"], [], False,
                       codex_identity="github-actions[bot]")
    check("sticky earlier bot trigger stays not delivered",
          "not delivered" in body)
    body = marker_body(state, d_sec, ["P1"], [], True,
                       codex_identity="nichm",
                       codex_state="completed")
    check("sticky codex completed when readable",
          "state: **completed**" in body)
    d_abs = decide(mk_bundle(files=src), plain, None)
    body = marker_body(state, d_abs, [], [], False)
    check("sticky abstained has no tier verdict",
          "⚪ **Jev: no verdict · model unavailable**" in body
          and "Model unavailable" in body
          and "Ship confidently" not in body)
    d_wave = dict(d_sec, wave_sibling={"repo": "webuildstuffio/y",
                                       "number": 9}, codex_post=False)
    body = marker_body(state, d_wave, ["P1"], [], False)
    check("sticky wave sibling note",
          "Wave sibling of `webuildstuffio/y#9`" in body
          and "escalation posted there" in body)
    check("questions include breakage + behavior",
          "breakage_risk" in build_questions(mk_bundle())
          and "changes_behavior" in build_questions(mk_bundle()))
    print("V23-TEST " + ("OK" if ok else "FAILED"))
    return 0 if ok else 1



if __name__ == "__main__":
    sys.exit(v23_tests())
