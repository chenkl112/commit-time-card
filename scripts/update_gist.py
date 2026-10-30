"""Sync the pinned public Gist without changing its ID or adding a description."""

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from update_commit_time import collect_counts


def render_text(counts):
    if len(counts) != 4 or any(count < 0 for count in counts) or not sum(counts):
        raise ValueError("Expected four nonnegative counts with a positive total")
    total = sum(counts)
    filename = "I'm an early 🐤" if sum(counts[:2]) >= sum(counts[2:]) else "I'm a night owl 🦉"
    labels = [("🌞", "Morning"), ("🌆", "Daytime"), ("🌃", "Evening"), ("🌙", "Night")]
    lines = []
    for (icon, label), count in zip(labels, counts):
        filled = round(count / total * 25)
        bar = "█" * filled + "░" * (25 - filled)
        lines.append(f"{icon} {label:<7} {count:>4} commits  {bar}  {count / total * 100:5.1f}%")
    return filename, "\n".join(lines)


def api(gist_id, token, payload=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "chenkl112-gist-daily-sync",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                f"https://api.github.com/gists/{gist_id}",
                data=data,
                headers=headers,
                method="PATCH" if payload is not None else "GET",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (OSError, ValueError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def synchronize(gist_id, token, counts):
    filename, content = render_text(counts)
    gist = api(gist_id, token)
    if gist["owner"]["login"].lower() != "chenkl112" or not gist["public"]:
        raise RuntimeError("Refusing to update a different account or a nonpublic Gist")
    if len(gist["files"]) != 1:
        raise RuntimeError("Expected exactly one Gist file; existing files preserved")
    old_name, old_file = next(iter(gist["files"].items()))
    changed = old_name != filename or old_file["content"] != content or gist.get("description") != ""
    if changed:
        api(gist_id, token, {
            "description": "",
            "files": {old_name: {"filename": filename, "content": content}},
        })
        gist = api(gist_id, token)
    if gist.get("description") != "" or set(gist["files"]) != {filename} or gist["files"][filename]["content"] != content:
        raise RuntimeError("Gist verification failed")
    return {
        "url": gist["html_url"],
        "filename": filename,
        "sample": sum(counts),
        "counts": counts,
        "changed": changed,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gist-id", required=True)
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--state-file", type=Path)
    args = parser.parse_args()
    token = args.token_file.read_text().strip() if args.token_file else os.environ.get("GIST_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing Gist credential")
    # This process never spawns children; the credential is not written to logs.
    os.environ["GITHUB_TOKEN"] = token
    result = synchronize(args.gist_id, token, collect_counts())
    if args.state_file:
        args.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.state_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(args.state_file)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
