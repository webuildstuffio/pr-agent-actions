#!/usr/bin/env python3
"""Offline self-test for the Jev v2.4.0 package (test-gap aim,
post-warrants-stamp, verdict-line coherence, effort margin).
Split out of jev_tag_test.py at creation (file-length limit).
Run: python3 jev_v24_test.py, exits non-zero on FAIL.

The test-gap cases are the recheck-v5 judged corpus itself
(~/workspace/jev-recheck-v5-2026-11-17): the 21 false firings
and the correct firings, replayed over the PRs' final file
lists with the recorded changes_behavior answers."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jev_layer1 import file_kind, is_test_path, test_gap
from jev_lib import decide
from jev_tag import apply_decision, marker_body
from jev_tag_test import FakeGh2, marker_comment


def v24_tests():
    ok = True

    def check(name, cond):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name)
        ok = ok and bool(cond)

    plain = {"hits": [], "any": False, "critical": False,
             "categories": [], "hard": False, "security_hard": False}

    def mk_bundle(files=(), **over):
        b = {"repo": "webuildstuffio/x", "pr_number": 3,
             "pr_title": "t", "pr_body": "", "pr_author": "a",
             "pr_labels": [],
             "files": [{"path": p, "additions": 5, "deletions": 5}
                       for p in files],
             "issue": None, "tier": "flagship", "readme": "",
             "agents": "", "repo_labels": None}
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

    def flag(files, cb=None, **ans_over):
        """decide().test_gap_flag for a bundle + behavior answer."""
        if cb is not None:
            ans_over["changes_behavior"] = {"type": "noul", "noul": cb}
        d = decide(mk_bundle(files), plain, mk_answers(**ans_over))
        return d["test_gap_flag"]

    # --- is_test_path: the Rust *_tests convention (v5 megamem)
    for p in ("engine/src/bm25_tests.rs",
              "engine/src/turboquant_tests.rs",
              "engine/src/config/registry_tests_query.rs",
              "engine/src/bm25_tests/a_sanitize_explain.rs",
              "engine/src/pipeline/fetch_tests/a_query_expansion.rs"):
        check(f"test path {p}",
              is_test_path([c for c in p.split("/") if c]))
    for p in ("src/contest.ts", "src/testament.ts", "src/latest.ts",
              "engine/src/pipeline/vecapi.rs"):
        check(f"not test path {p}",
              not is_test_path([c for c in p.split("/") if c]))

    # --- file_kind: config basenames and data files (v5)
    check("next.config.js is config",
          file_kind("next.config.js") == "config")
    check("vite.config.ts is config",
          file_kind("vite.config.ts") == "config")
    check("src/config/types.rs stays behavior",
          file_kind("src/config/types.rs") == "behavior")
    check("data dir file is data",
          file_kind("src/data/activecalculators/ocado-smart-pass.ts")
          == "data")
    check("plain source stays behavior",
          file_kind("src/lib/analytics.ts") == "behavior")

    # --- test-gap replay: v5 false firings must not flag
    check("megamem #479 test-only splits: no flag",
          not flag(["engine/src/bm25_tests.rs",
                    "engine/src/bm25_tests/a_sanitize_explain.rs",
                    "engine/src/pipeline/fetch_tests.rs",
                    "engine/src/pipeline/fetch_tests/a_query_expansion.rs"],
                   cb=0.1))
    check("megamem #471 clippy bundle with *_tests.rs: no flag",
          not flag(["engine/src/bm25/query_builder.rs",
                    "engine/src/turboquant_tests.rs"], cb=0.9))
    check("megamem #478 verbatim split, behavior no: gated",
          not flag(["engine/src/cli/cmd_doctor.rs",
                    "engine/src/cli/cmd_doctor/embed_server.rs"],
                   cb=0.1))
    check("folio #3395 docs + comment pointers, behavior no: gated",
          not flag(["AGENTS.md", "src/lib/ai/models.ts"], cb=0.1))
    check("powerloss #992 config-only: no hard gap",
          test_gap(mk_bundle(["config/last-updated.generated.ts",
                              "next.config.js"]))["status"] is None)
    check("upgrade.tools #859 data-only: no hard gap",
          test_gap(mk_bundle(
              ["src/data/activecalculators/ocado-smart-pass.ts"])
          )["status"] is None)
    check("termlimits #322 consolidation, behavior no: gated",
          not flag(["components/seo-head.tsx", "pages/index.tsx"],
                   cb=0.1))

    # --- test-gap replay: v5 correct firings must still flag
    check("dealt #274 source-only, behavior yes: flag",
          flag(["src/client-errors/client-errors.js"], cb=0.9))
    check("folio #3391 components, behavior yes: flag",
          flag(["src/app/(dashboard)/dashboard-page-client.tsx",
                "src/components/dashboard/dashboard-stats-grid.tsx"],
               cb=0.9))
    check("megamem #482 rust sources, behavior yes: flag",
          flag(["engine/src/bm25/query_builder.rs",
                "engine/src/conv.rs"], cb=0.9))
    check("no behavior answer never suppresses",
          flag(["src/lib/ai/models.ts"], cb=None))
    check("gate is recorded on the decision",
          decide(mk_bundle(["src/lib/ai/models.ts"]), plain,
                 mk_answers(changes_behavior={"type": "noul",
                                              "noul": 0.1}))
          ["test_gap_behavior_gate"] is True)

    # --- post warrants the stamp (torontocrimescore divergence)
    toronto = decide(
        mk_bundle(["src/lib/signing.ts"]),
        plain,
        mk_answers(
            security_related={"type": "noul", "noul": 0.82},
            security_category={"type": "choice", "choice": "none",
                               "probabilities": {"none": 0.9}}))
    check("toronto shape: post fires at P 0.82 category none",
          toronto["codex_post"] is True)
    check("toronto shape: post warrants type:security",
          toronto["security_type_warranted"] is True
          and "type:security" in toronto["labels_desired"])
    check("mid P + category none + no post: still no stamp",
          decide(mk_bundle(["src/lib/x.ts"]), plain,
                 mk_answers(
                     security_related={"type": "noul", "noul": 0.5},
                     security_category={
                         "type": "choice", "choice": "none",
                         "probabilities": {"none": 0.9}}))
          ["security_type_warranted"] is False)

    # --- verdict-line coherence: Deep + L1 names the human review
    state = {"pr_applied": [], "issue_applied": [],
             "issue_number": None, "codex_posted": False,
             "codex_standalone_posted": False, "runs": 1}
    d_deep_l1 = {"abstained": False, "ship_tier": "Deep review required",
                 "review_level": 1,
                 "review_level_name": "L1 (Codex general)",
                 "security_band": "low", "p_security_jev": 0.1,
                 "blast_radius": 3, "security_category": None,
                 "layer1": plain, "codex_post": False,
                 "breakage_risk": 3, "p_changes_behavior": 0.9,
                 "p_perf_risk": None, "perf_flag": False,
                 "test_gap_flag": False, "themes": [], "effort": None,
                 "escalation": {}}
    body = marker_body(state, d_deep_l1, [], [], False)
    check("Deep + L1 verdict line names human deep review",
          "Deep review required · Review level L1 (Codex general)"
          " + human deep review" in body)
    d_deep_l2 = dict(d_deep_l1, review_level=2,
                     review_level_name="L2 (Codex security)",
                     codex_post=True)
    body2 = marker_body(state, d_deep_l2, [], [], True)
    check("Deep + L2 verdict line unchanged",
          "human deep review" not in body2.split("\n")[1])
    check("sticky footer carries v2.4.0",
          "jev-tag v2.4.0" in body)

    # --- effort margin instrumentation (P5 refit data)
    d_eff = decide(mk_bundle(), plain, mk_answers(
        effort={"type": "choice", "choice": "effort:s",
                "probabilities": {"effort:s": 0.7, "effort:m": 0.2,
                                  "effort:xs": 0.1}}))
    check("effort winner probability recorded",
          abs(d_eff["effort_p"] - 0.7) < 1e-9)
    check("effort margin is winner minus runner-up",
          abs(d_eff["effort_margin"] - 0.5) < 1e-9)
    check("effort bar unchanged at 0.60",
          d_eff["effort"] == "effort:s")
    d_eff1 = decide(mk_bundle(), plain, mk_answers(
        effort={"type": "choice", "choice": "effort:s",
                "probabilities": {"effort:s": 0.7}}))
    check("effort margin is None with no runner-up",
          d_eff1["effort_margin"] is None)
    d_eff0 = decide(mk_bundle(), plain, mk_answers())
    check("effort_p is None when the model never answered effort",
          d_eff0["effort_p"] is None and d_eff0["effort_margin"] is None)

    # --- rerun clears a stale effort pair (Codex P2 on PR 64)
    prior = {"pr_applied": [], "issue_applied": [], "codex_posted": False,
             "codex_standalone_posted": False, "runs": 1,
             "effort_p": 0.7, "effort_margin": 0.5}
    bundle_r = {"repo": "o/r", "pr_number": 7, "pr_labels": [],
                "issue": None}
    d_rerun = {"labels_desired": [], "codex_post": False,
               "security_band": "low", "p_security_jev": 0.1,
               "layer1": plain, "ship_tier": None, "review_level": 1,
               "effort_p": 0.9, "effort_margin": None, "escalation": {}}
    class PatchGh(FakeGh2):
        """FakeGh2 + records PATCHed sticky bodies too."""

        def __init__(self, **kw):
            super().__init__(**kw)
            self.patches = []

        def call(self, method, path, body=None, ok_missing=False):
            if method == "PATCH":
                self.patches.append(body)
                return {}
            return super().call(method, path, body, ok_missing)

    gh_r = PatchGh(comments=[marker_comment(prior)])
    apply_decision(gh_r, bundle_r, d_rerun)
    posted = gh_r.patches[0]["body"]
    check("rerun updates effort_p and clears stale effort_margin",
          '"effort_p":0.9' in posted.replace(" ", "")
          and "effort_margin" not in posted)

    # --- trunc_bytes honours its byte limit incl. the marker (Qodo)
    from jev_state import trunc_bytes
    big = "x" * 5000
    check("trunc_bytes result stays within the byte limit",
          len(trunc_bytes(big, 100).encode("utf-8")) <= 100
          and trunc_bytes(big, 100).endswith("[truncated]"))
    check("trunc_bytes leaves short text untouched",
          trunc_bytes("short", 100) == "short")

    # --- security state budget counts snippet headers (Qodo PR 64)
    from jev_state import STATE_BUDGET, build_security_state
    many = [{"path": ".github/workflows/" + "x" * 60 + f"-{i}.yml",
             "additions": 5, "deletions": 5, "patch": "p" * 5000}
            for i in range(12)]
    sec_state = build_security_state(mk_bundle(files=()), plain)
    b_many = mk_bundle()
    b_many["files"] = many
    sec_state = build_security_state(b_many, plain)
    check("security state never exceeds STATE_BUDGET",
          len(sec_state.encode("utf-8")) <= STATE_BUDGET)

    print("V24-TEST " + ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(v24_tests())
