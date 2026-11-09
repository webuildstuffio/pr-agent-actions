# pr-agent-actions

Public home of the two composite actions the webuildstuffio fleet's
Qodo review workflow (`qodo-review.yml`, canonical source:
webuildstuffio/gh-actions-and-skills) loads with `uses:` at a pinned
full SHA:

- `qodo-config/` — delivers the org-global pr-agent configuration
  into a caller job's workspace as `.pr_agent.global.toml`, which
  the workflow hands to pr-agent via `config.extra_config_url`.
- `jev/` — the Jev PR tagging action (labels + Codex security
  review trigger).

## Why this repo is public and split from pr-agent-settings

GitHub resolves a `uses:` action reference itself, before any step
runs, and a public consumer repo (webuildstuffio/XZ-Mods) can never
resolve an action from a private repo; no token can be passed for
action resolution. The actions contain no tuning and no secrets, so
they live here, public, where every consumer can resolve them.

The tuned configuration itself (`.pr_agent.toml`) is NOT here. It
stays in webuildstuffio/pr-agent-settings and is distributed as a
private GitHub Packages container package,
`ghcr.io/webuildstuffio/pr-agent-config`, published by a workflow
in pr-agent-settings on every config change. `qodo-config` (v2+)
pulls that package with the caller job's own `GITHUB_TOKEN` and
extracts the toml. A consumer repo therefore needs a one-time
"Manage Actions access" grant on the package before its workflows
can pull it; no PATs or distributed secrets are involved.

History: both actions were moved here verbatim from
webuildstuffio/pr-agent-settings at the exact commits the fleet
pinned (qodo-config at 72eccac3b473975585959eba86e37ae973229940,
jev at 5409839a33f0789d5388e275f82695ce3ec98bb5) so the split could
land without a behaviour change; qodo-config then moved to the
package transport as v2.0.0 in this repo.
