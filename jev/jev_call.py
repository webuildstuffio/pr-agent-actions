#!/usr/bin/env python3
"""The Decisions API call for jev_tag.py: endpoint constants,
JevError, and call_jev with its v2.2.0 retry/backoff. Split out
of jev_lib.py in v2.3.0 (file-length limit); jev_lib re-exports
everything here. Python 3 standard library only."""

import json
import os
import time
import urllib.error
import urllib.request

from jev_sheet import QUESTIONS


JEV_URL = "https://openrouter.ai/api/alpha/decisions"
JEV_MODEL = os.environ.get("JEV_MODEL", "typesafe/jev-1.14")


class JevError(Exception):
    pass


JEV_ATTEMPTS = 3              # total attempts per call (v2.2.0 retry)
JEV_TIMEOUT = 20              # seconds per attempt (was: one 90s try)
JEV_BACKOFF = 2.0             # base seconds; doubles per retry


def _call_jev_once(state, api_key, questions, timeout):
    """A single Decisions API attempt. Raises JevError on any
    HTTP, network, or malformed-response failure."""
    payload = {"model": JEV_MODEL, "state": state,
               "questions": questions or QUESTIONS}
    req = urllib.request.Request(
        JEV_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "jev-tag/1.0",
        },
        method="POST")
    try:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- req targets the hardcoded https JEV_URL constant; only the JSON payload varies
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as exc:
        raise JevError(f"Jev HTTP {exc.code}")
    except Exception as exc:
        raise JevError(f"Jev call failed: {exc}")
    if not isinstance(data.get("answers"), dict):
        raise JevError("Jev response has no answers object")
    return data


def call_jev(state, api_key, questions=None, attempts=JEV_ATTEMPTS,
             timeout=JEV_TIMEOUT, _sleep=None, _once=None):
    """One Decisions API request, retried with backoff (v2.2.0).

    The pre-2.2.0 single 90s attempt degraded 12.3% of runs in the
    audit window and every degraded run applied a wrong fallback
    set. Retries are bounded (3 attempts at ~20s), so the worst
    case inside the Qodo job is about a minute, not 4.5 minutes of
    naive 90s retries. Raises JevError after the last attempt; the
    caller then ABSTAINS (see decide())."""
    if not api_key:
        raise JevError("OPENROUTER_API_KEY is not set")
    sleep = _sleep if _sleep is not None else time.sleep
    once = _once if _once is not None else _call_jev_once
    last = None
    for i in range(max(1, attempts)):
        try:
            return once(state, api_key, questions, timeout)
        except JevError as exc:
            last = exc
            if i + 1 < max(1, attempts):
                sleep(JEV_BACKOFF * (2 ** i))
    raise last




