#!/usr/bin/env python3
"""Marker + Codex-state parsing for jev_tag.py: the jev-tag
marker comment (human-veto and one-shot state) and Codex's
review-state comment. Split out of jev_tag.py in v2.3.0
(file-length limit); jev_tag re-exports everything here.
Python 3 standard library only."""

import json
import re


MARKER_RE = re.compile(r"<!-- jev-tag:v1 (\{.*?\}) -->", re.DOTALL)


def find_marker(comments, extra_authors=()):
    """(comment, state dict) of the newest jev-tag marker comment.

    Trusted authors: github-actions[bot] plus any `extra_authors`
    (the JEV_MENTION_PAT owner's login, resolved from the token
    itself; that human is the label-floor authority). Anyone else
    could forge state to suppress the Codex trigger or veto."""
    trusted = {"github-actions[bot]"} | set(extra_authors)
    for c in reversed(comments):
        if (c.get("user") or {}).get("login") not in trusted:
            continue
        m = MARKER_RE.search(c.get("body") or "")
        if m:
            try:
                return c, json.loads(m.group(1))
            except ValueError:
                continue
    return None, {"pr_applied": [], "issue_applied": [],
                  "issue_number": None, "codex_posted": False,
                  "codex_standalone_posted": False,
                  "runs": 0}


def codex_security_state(comments):
    """Codex's own security_review status from its review-state
    comment, when one is readable; None otherwise. Only the
    Codex connector's own comments count: the state block is
    plain comment text, so any other author could forge a
    "completed" the sticky would then display as Codex's word.
    Defensive: any shape surprise reads as unreadable, never
    as a state."""
    for c in reversed(comments or []):
        if ((c.get("user") or {}).get("login")
                != "chatgpt-codex-connector[bot]"):
            continue
        body = c.get("body") or ""
        if "codex-review-state" not in body:
            continue
        m = re.search(r"codex-review-state:v1\s*", body)
        if not m:
            continue
        # Balanced-brace extraction: the state object nests
        # ({"security_review": {"status": ...}}), so a
        # non-greedy regex would truncate at the first brace.
        start = body.find("{", m.end())
        if start < 0:
            continue
        depth, end = 0, None
        in_str, esc = False, False
        for i in range(start, len(body)):
            ch = body[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            continue
        try:
            data = json.loads(body[start:end])
        except ValueError:
            continue
        sr = data.get("security_review")
        if isinstance(sr, dict):
            val = sr.get("status") or sr.get("state")
            if isinstance(val, str) and val:
                return val
        elif isinstance(sr, str) and sr:
            return sr
    return None


