# Jev PR tagging (pilot)

`jev_tag.py` is the fleet's Jev decision-model tagging step (decision
logic in `jev_lib.py`, imported by it; offline checks in
`jev_tag_test.py`). It runs as its own `Jev tagging` job in wired
repos' `qodo-review.yml` (current wiring v3.9.4; it was the first
step of the `suggest` job until the v3.6.1 job split below), in
parallel with the pr-agent job, so its labels, security trigger,
and sticky comment land independently of the suggestions run:

1. Gathers PR state (PR text, changed files, linked issue, repo tier
   from the `rr-tier` property, README + AGENTS.md excerpts).
2. Runs deterministic Layer 1 path rules: directory semantics over
   changed paths (auth, secrets, payments, data-PII, infra,
   dependency manifests, sensitive filenames such as `.env*`,
   `*.pem`, `*.key`, `credentials*`), yielding per-category evidence
   lists. There is no text or keyword scan; Jev reads the text
   itself.
3. Asks Jev (`typesafe/jev-1.14`, OpenRouter Decisions API) one request
   with the full label job sheet (security, type, priority, themes,
   effort, owner labels, plus record-only Codex-worth and low-risk
   signals), with the Layer 1 evidence shown as facts, not
   conclusions.
4. Adds schema-v4.2 labels to the PR and its linked issue. Since
   v2.2.0 the security questions are re-asked in a dedicated call
   whose state adds targeted patch snippets for security-relevant
   files, and its answers govern the security decision. When the
   post rule fires (a security route plus model concurrence at
   P >= 0.40, or a critical-filename hit), the
   `@codex security review` trigger is rendered once as a
   delimited section inside the sticky comment, with Jev's focus
   lines, AND posted once as a standalone comment containing only
   the trigger line: controlled probes (repo-review #680,
   megahealth #131) proved Codex ignores the in-sticky mention
   and answers the standalone one. The sticky is
   created and PATCHed with the `JEV_MENTION_PAT` org secret when
   the wiring passes it through, so the sticky and the mention in
   it are authored by the owner's account (a connected Codex
   user) instead of github-actions[bot], whose mentions Codex
   ignores; without the secret everything runs on the workflow
   token as before. The type:security label
   additionally requires a warrant: a hard path hit, or Jev's own
   verdict with category agreement (its category answer is not
   "none") at mid band or higher, or a high-confidence
   secrets-in-text detection, or (since v2.4.0) a fired Codex
   post: the post rule is the stricter gate, so a PR that earns
   a security review carries the type. A bare mid-band
   probability with category "none" that earns no post still
   bands the PR without applying the security type.

Guardrails: Jev can only upgrade security, never downgrade a Layer 1
hit or a human label; the step never removes labels; labels a human
removes after the step applied them are never re-added on that PR
(tracked in a `<!-- jev-tag:v1 ... -->` marker comment); priority is
clamped by repo tier; the step fails open (warning + exit 0) so it can
never break the Qodo job. Since v2.2.0 the model call retries
(3 attempts, ~20s timeouts, backoff) and a run whose call still
fails ABSTAINS: it applies nothing beyond a Layer 1 security stamp
and flags the sticky as model-unavailable, instead of applying the
manufactured fallback set the 2026-11-03 audit scored wrong 24 of
24. Also since v2.2.0: a docs-only PR cannot earn a model-route
security stamp (prose about security is not a security change);
an infrastructure directory hit alone is evidence-only; and
session words are scoped out of test paths. (A manifest
version-diff sub-rule was built and dropped before release: the
pilot replay showed it removing warranted stamps.)

## How wired repos load the script

Since jev-action v1.0.0 (2026-11-04), the step is packaged as a
composite action (`jev/action.yml` in this repo). Since the
2026-11-08 privacy split, wired repos load the port in the public
`webuildstuffio/pr-agent-actions` repo by full commit SHA:

```yaml
uses: webuildstuffio/pr-agent-actions/jev@<full-40-char-SHA>
```

(a public consumer repo can never resolve an action from a
private repo). This repo self-hosts: its own wiring pins a local
checkout of this directory instead. The full-SHA pin is the
integrity mechanism.

History: the v1/v2 wiring fetched the two files over their
`raw.githubusercontent.com` URLs at a pinned SHA and verified SHA256
digests before executing. That only worked while this repo was
public; once it went private the fetch returned 404, the step's
fail-open design absorbed the error silently, and Jev processed
nothing fleet-wide from 2026-11-01 16:41Z until the v1.0.0 packaging
fix (issue #42). The digest check retired with the raw fetch. The
wiring (template v3.6.1) also moved Jev out of the `suggest` job
into its own job: a `uses:` reference resolves when its job is
prepared, before any step runs, so as a step an unresolvable pin
failed the whole Qodo job at preparation and no suggestion ever
ran (probe folio-app#3233). As its own job, a load failure fails
only that job and surfaces on the PR as a failed `Jev tagging`
check; a step-level failure posts the same check via the API from
a follow-up step. The job is continue-on-error and never gates a
merge, so Jev can never pass silently or block Qodo again.

## Updating

Edit the script here, merge, port the change to
`webuildstuffio/pr-agent-actions`, then bump the pinned SHA in each
wired repo's `qodo-review.yml` `uses:` line to the port's merge
commit. One exception: this repo's own wiring pins the SHA in a
checkout `ref:` and references the action by local path
(`./.jev-pinned/jev`), because a workflow cannot download its own
repo's action archive (the codeload fetch 404s at a valid SHA;
proven 2026-11-04). The packaging carries its own version note
(the header comment in `jev/action.yml`, currently jev-action
v1.3.0; packaging changes bump it, decision-logic changes do
not). The step carries a
version (`VERSION` in `jev_lib.py`, currently v2.4.0; the v1 to v2
jump marks the warrant gate plus the paths-only Layer 1, whose
decisions are not comparable to v1 runs; v2.0.1 tokenizes dotted
compound stems such as auth.service.ts; v2.1.0 folds the Codex
mention into the sticky comment and adds the JEV_MENTION_PAT
owner-identity sticky path; v2.2.0 is the top-5 improvement
package: retry + abstain, the docs-only gate, Layer 1 refinement,
the standalone Codex comment, and the dedicated security call
with escalation concurrence; v2.3.0 adds wave dedupe for
escalation posting (same normalized title + identical file-path
set across repos within about 24 hours posts on the first
instance only, critical hits always post), the Risk to ship
composite (breakage_risk score plus changes_behavior noul
feeding a deterministic ship tier and review levels L0-L4 in
decide(); record-only, printed in the sticky, never a merge
gate), the test-gap Layer 1 rule plus tests_cover_change noul
(sticky line only), and the sticky verdict-first redesign with
the Codex delivery state printed honestly; v2.4.0 is the
recheck-v5 package: the test-gap flag is suppressed when Jev's
own changes_behavior answer says no runtime behavior change,
Rust `*_tests` paths classify as tests, and `*.config.*`
basenames and `data/` files classify as config/data instead of
behavior; a fired Codex post now also warrants the security
type; the Deep + L1 verdict line names the human deep review it
calls for; and the effort winner probability and margin are
persisted in the marker so the abstention refit has data. The
two post-route widenings proposed after recheck v3 were
replay-rejected (see the VERSION comment in `jev_lib.py`) and
are deliberately not in v2.4.0). Wirings stamp the version
as a `# jev-tag v2.4.0` comment above the step and the sticky comment
footer shows it. Mode is controlled per repo by the `JEV_TAG_MODE`
repository variable (`dry-run` or `apply`; default `apply` when
unset). Python 3 standard library only.
Self-test: `python3 jev/jev_tag_test.py`.
