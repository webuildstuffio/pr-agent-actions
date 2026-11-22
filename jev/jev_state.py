#!/usr/bin/env python3
"""State assembly for jev_tag.py: the byte-budget truncation
helper and the two Jev `state` builders (the main call's state
and the dedicated security call's snippet-enriched state).
Split out of jev_lib.py in v2.4.0 (file-length limit); jev_lib
re-exports everything here. Python 3 standard library only."""

from jev_layer1 import DEP_MANIFESTS, repo_specialties


STATE_BUDGET = 27000          # bytes; Jev long-context mode starts ~32k


def trunc_bytes(text, limit):
    """Truncate a string to at most `limit` UTF-8 bytes, safely."""
    if text is None:
        return ""
    raw = text.encode("utf-8", "ignore")
    if len(raw) <= limit:
        return text
    marker = "\n[truncated]"
    keep = max(0, limit - len(marker.encode("utf-8")))
    return raw[:keep].decode("utf-8", "ignore") + marker


def build_state(bundle, l1):
    """Assemble the Jev `state` text, capped under the long-context
    threshold (~32k bytes). Bodies are trimmed first."""
    issue = bundle["issue"] or {}
    parts = []
    parts.append(f"Repository: {bundle['repo']} (fleet tier: {bundle['tier']})")
    parts.append(f"Pull request #{bundle['pr_number']} by {bundle['pr_author']}: {bundle['pr_title']}")
    parts.append("PR description:\n" + trunc_bytes(bundle["pr_body"] or "(empty)", 6000))
    if issue:
        parts.append(f"Linked issue #{issue['number']}: {issue['title']}")
        parts.append("Issue description:\n" + trunc_bytes(issue["body"] or "(empty)", 6000))
    lines = [f"{f['path']} (+{f['additions']} -{f['deletions']})"
             for f in bundle["files"]]
    files_text = "\n".join(lines) if lines else "(none)"
    if bundle.get("files_truncated"):
        files_text += "\n(note: file list hit the API cap; may be incomplete)"
    parts.append("Changed files:\n" + trunc_bytes(files_text, 6000))
    evidence = l1.get("evidence") or {}
    if evidence:
        lines = [f"- {cat}: {', '.join(paths)}"
                 for cat, paths in sorted(evidence.items())]
        parts.append(
            "Deterministic evidence (facts only: these changed-file "
            "paths matched deterministic path categories (security, "
            "data, infra, dependencies); they are not conclusions, "
            "whether the change is actually security-related is "
            "for the questions to judge):\n"
            + "\n".join(lines))
    else:
        parts.append(
            "Deterministic evidence: no changed file matched a "
            "security-relevant path category.")
    if bundle["readme"]:
        parts.append("Repository README excerpt:\n" + trunc_bytes(bundle["readme"], 2500))
    if bundle["agents"]:
        parts.append("Repository AGENTS.md excerpt:\n" + trunc_bytes(bundle["agents"], 2500))
    catalog = repo_specialties(bundle.get("repo_labels"))
    if catalog:
        # The FULL specialty list from the repo's live labels (the
        # only specialty labels Jev may pick). Descriptions are
        # dropped first if the section would crowd out the budget.
        head = ("Repository specialty labels (repo-specific; the only "
                "non-generic labels that exist in this repo):\n")
        section = head + "\n".join(
            f"- {n}: {d}" if d else f"- {n}"
            for n, d in sorted(catalog.items()))
        if len(section.encode("utf-8")) > 5000:
            section = head + "\n".join(sorted(catalog))
        parts.append(trunc_bytes(section, 5000))
    return trunc_bytes("\n\n".join(parts), STATE_BUDGET)


SNIPPET_TOTAL_BUDGET = 8000   # bytes of patch text, security call
SNIPPET_PER_FILE = 2000       # bytes per file


def _security_relevant(path, l1):
    """A file whose patch belongs in the security call's state:
    a workflow file, a dependency manifest, or any file with a
    Layer 1 category hit."""
    comps = [c for c in path.lower().split("/") if c]
    if comps[:2] == [".github", "workflows"]:
        return True
    if comps and comps[-1] in DEP_MANIFESTS:
        return True
    evidence = (l1 or {}).get("evidence") or {}
    return any(path in paths for paths in evidence.values())


def build_security_state(bundle, l1):
    """State for the dedicated security call: the main state
    trimmed so the total stays under STATE_BUDGET, plus a patch
    snippet section (security-relevant files only, deletions
    included, capped per file and in total)."""
    base = build_state(bundle, l1)
    room = STATE_BUDGET - SNIPPET_TOTAL_BUDGET - 200
    base = trunc_bytes(base, room)
    snippets = []
    used = 0
    for f in bundle.get("files") or []:
        patch = f.get("patch")
        if not patch or not _security_relevant(f["path"], l1):
            continue
        if used >= SNIPPET_TOTAL_BUDGET:
            break
        cap = min(SNIPPET_PER_FILE, SNIPPET_TOTAL_BUDGET - used)
        text = trunc_bytes(patch, cap)
        block = f"--- {f['path']}\n{text}"
        snippets.append(block)
        # Count the header line too: `used` must bound the whole
        # snippet section, not just patch bytes (Qodo, PR 64).
        used += len(block.encode("utf-8")) + 1
    if not snippets:
        return base
    return trunc_bytes(
        base + ("\n\nPatch snippets for security-relevant files "
                "(unified diff excerpts; judge what the change "
                "actually does, not just the path):\n"
                + "\n".join(snippets)), STATE_BUDGET)
