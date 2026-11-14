#!/usr/bin/env python3
"""Wave-dedupe production adapter for jev_tag.py (v2.3.0, G8):
the org-wide search and per-candidate checks behind
pick_wave_leader, plus the delivery-identity helpers. Split
out of jev_tag.py in v2.3.0 (file-length limit); jev_tag
re-exports everything here. Python 3 standard library only."""

import urllib.parse
from datetime import datetime, timedelta

from jev_gh import GhError
from jev_lib import pick_wave_leader
from jev_marker import find_marker


def standalone_delivered(comments, state):
    """True when the sibling's escalation was DELIVERABLE: its
    marker claims the post, and the standalone trigger comment
    itself is human-authored. A bot-authored standalone sets the
    same marker flags but triggers nothing (Codex ignores bot
    mentions), so a bot-posted sibling must never suppress a
    later sibling whose post would actually land."""
    if not (state.get("codex_posted")
            or state.get("codex_standalone_posted")):
        return False
    for c in comments or []:
        if (c.get("body") or "").strip() != "@codex security review":
            continue
        author = ((c.get("user") or {}).get("login") or "")
        if author and not author.endswith("[bot]"):
            return True
    return False


def trigger_author(comments):
    """Author of the existing standalone trigger comment, or
    None. The delivery identity for an earlier request comes
    from THIS comment, never from the current run's credential:
    a human trigger posted before the PAT reached a repo is
    delivered even when today's run has no PAT, and a bot
    trigger stays undelivered even after a PAT arrives."""
    for c in comments or []:
        if (c.get("body") or "").strip() != "@codex security review":
            continue
        author = ((c.get("user") or {}).get("login") or "")
        if author:
            return author
    return None


def find_wave_leader(gh, bundle, mention_login=None):
    """Production adapter for pick_wave_leader (v2.3.0, G8):
    org-wide title search for same-title PRs, then per-candidate
    file-set and marker checks. The caller passes the widest
    credential it has (the mention PAT client when wired, else
    the workflow token): a repo-scoped GITHUB_TOKEN cannot read
    other repos, so cross-repo discovery only reaches as far as
    that credential does, and unreadable candidates are skipped
    individually (one bad candidate never aborts the search).
    Fail-open: any API failure reads as no leader, so the post
    proceeds as before."""
    repo = bundle["repo"]
    org = repo.split("/", 1)[0]
    title = bundle.get("pr_title") or ""
    if not title or not bundle.get("pr_created_at"):
        return None
    try:
        self_time = datetime.fromisoformat(
            bundle["pr_created_at"].replace("Z", "+00:00"))
    except ValueError:
        return None
    since = (self_time - timedelta(hours=24)).date().isoformat()
    q = urllib.parse.quote(
        f'"{title}" in:title type:pr org:{org} created:>={since}',
        safe="")
    resp = gh.call("GET", f"/search/issues?q={q}")
    items = (resp or {}).get("items") or []
    # Window-filter BEFORE the cap: a recurring title can have
    # many historical matches, and taking the oldest 10 first
    # would crowd out the current wave's sibling entirely.
    cutoff = self_time - timedelta(hours=24)
    fresh = []
    for item in items:
        try:
            t = datetime.fromisoformat(
                (item.get("created_at") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if t >= cutoff:
            fresh.append(item)
    items = sorted(fresh, key=lambda i: i.get("created_at") or "")[:10]
    paths = [f["path"] for f in bundle.get("files") or []]
    candidates = []
    for item in items:
        rurl = item.get("repository_url") or ""
        crepo = rurl.split("/repos/", 1)[-1] if "/repos/" in rurl \
            else ""
        number = item.get("number")
        if not crepo or not number or (
                crepo == repo and number == bundle["pr_number"]):
            continue
        try:
            files = gh.get_all(f"/repos/{crepo}/pulls/{number}/files")
            comments = gh.get_all(
                f"/repos/{crepo}/issues/{number}/comments")
        except GhError:
            continue
        _, st = find_marker(
            comments, [mention_login] if mention_login else ())
        candidates.append({
            "repo": crepo, "number": number,
            "title": item.get("title") or "",
            "paths": [f.get("filename") or "" for f in files],
            "created_at": item.get("created_at") or "",
            "posted": standalone_delivered(comments, st),
        })
    return pick_wave_leader(
        candidates, (repo, bundle["pr_number"]), title, paths,
        bundle["pr_created_at"])


