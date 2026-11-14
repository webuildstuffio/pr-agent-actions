#!/usr/bin/env python3
"""GitHub API client for jev_tag.py: Gh + GhError. Split out
of jev_tag.py in v2.3.0 (file-length limit); jev_tag re-exports
both. Python 3 standard library only."""

import json
import urllib.error
import urllib.request


GH_API = "https://api.github.com"


class GhError(Exception):
    pass


class Gh:
    def __init__(self, token):
        self.token = token

    def call(self, method, path, body=None, ok_missing=False):
        url = path if path.startswith("http") else GH_API + path
        data = None
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "jev-tag/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method=method)
        try:
            # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- req targets the hardcoded https GH_API constant; only the API path suffix varies
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8", "ignore")
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as exc:
            if ok_missing and exc.code == 404:
                return None
            raise GhError(f"{method} {path} -> HTTP {exc.code}")
        except Exception as exc:  # network, timeout, JSON
            raise GhError(f"{method} {path} -> {exc}")

    def get_all(self, path, limit_pages=30):
        """GET a list endpoint, following ?page= pagination. The cap
        matches the GitHub API's own ceilings (e.g. 3,000 files per
        PR); callers that care check for a full-cap result."""
        out = []
        sep = "&" if "?" in path else "?"
        for page in range(1, limit_pages + 1):
            chunk = self.call("GET", f"{path}{sep}per_page=100&page={page}")
            if not isinstance(chunk, list):
                break
            out.extend(chunk)
            if len(chunk) < 100:
                break
        return out


