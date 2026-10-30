"""Build a commit-time card from up to 1,000 indexed public GitHub commits."""

import json
import math
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path


def fetch_page(page):
    url = (
        "https://api.github.com/search/commits?q=author%3Achenkl112"
        f"&sort=author-date&order=desc&per_page=100&page={page}"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "chenkl112-profile",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=headers), timeout=30
            ) as response:
                data = json.load(response)
            if data.get("incomplete_results"):
                raise RuntimeError("GitHub search returned incomplete results")
            return data
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def collect_counts():
    first = fetch_page(1)
    total = min(first["total_count"], 1000)
    items = list(first["items"])
    for page in range(2, math.ceil(total / 100) + 1):
        items.extend(fetch_page(page)["items"])
    commits = {item["sha"]: item for item in items}
    counts = [0, 0, 0, 0]
    for item in commits.values():
        date = datetime.fromisoformat(
            item["commit"]["author"]["date"].replace("Z", "+00:00")
        ).astimezone(timezone(timedelta(hours=8)))
        counts[((date.hour - 6) % 24) // 6] += 1
    if not sum(counts):
        raise RuntimeError("No public commits found; existing card preserved")
    return counts


def render(counts):
    total = sum(counts)
    early = sum(counts[:2]) >= sum(counts[2:])
    title = "I'm an early" if early else "I'm a night owl"
    labels = ["Morning", "Daytime", "Evening", "Night"]
    icons = [
        '<g stroke="#ffc857" stroke-width="1.4"><circle r="3.5" fill="#ffc857"/><path d="M0-7V-5M0 5V7M-7 0H-5M5 0H7M-5-5-3.5-3.5M3.5 3.5 5 5M-5 5-3.5 3.5M3.5-3.5 5-5"/></g>',
        '<path d="M-7 5V-4H-3V5M-1 5V-7H3V5M5 5V-1H8V5" fill="#9878cf"/><circle cx="6" cy="-5" r="2" fill="#ffc857"/>',
        '<path d="M-7 6V-3H-3V6M-1 6V-6H3V6M5 6V0H8V6" fill="#8c77bd"/><path d="M-6-8V-4M-8-6H-4M6-7V-3M4-5H8" stroke="#e4bf7a"/>',
        '<path d="M3-7A7 7 0 1 0 7 4A8 8 0 0 1 3-7" fill="#ffd580"/>',
    ]
    bird = (
        '<circle cx="0" cy="2" r="7" fill="#ffc857"/><circle cx="4" cy="-4" r="5" fill="#ffd580"/><circle cx="5" cy="-5" r="1" fill="#22292f"/><path d="m8-4 5 2-5 1M-3 9V12M1 9V12" stroke="#e99640" stroke-width="2"/>'
        if early else
        '<path d="M-8-8-6-3A9 9 0 1 0 6-3L8-8 2-5H-2Z" fill="#bc8d60"/><circle cx="-4" cy="0" r="4" fill="#f0d9a0"/><circle cx="4" cy="0" r="4" fill="#f0d9a0"/><circle cx="-4" cy="0" r="1.8" fill="#22292f"/><circle cx="4" cy="0" r="1.8" fill="#22292f"/><path d="m-2 4 2 3 2-3" fill="#ffc857"/>'
    )
    rows = []
    for index, (label, count) in enumerate(zip(labels, counts)):
        y = 100 + index * 28
        percent = count / total * 100
        bars = []
        for segment in range(40):
            color = "#c9d1d9" if segment < round(percent / 100 * 40) else "#444c56"
            bars.append(f'<rect x="{294 + segment * 4.5}" y="{y - 11}" width="3.5" height="14" fill="{color}"/>')
        rows.append(
            f'<text x="44" y="{y}" fill="#8b949e">{index + 1}</text>'
            f'<g transform="translate(77,{y - 4})">{icons[index]}</g>'
            f'<text x="98" y="{y}">{label}</text>'
            f'<text x="194" y="{y}">{count:>4} commits</text>'
            + "".join(bars)
            + f'<text x="490" y="{y}">{percent:5.1f}%</text>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="246" viewBox="0 0 600 246" role="img" aria-labelledby="title desc">'
        f'<title id="title">{escape(title)}</title>'
        f'<desc id="desc">Commit times for chenkl112. {total} latest indexed public commits, UTC+8. Morning 06–12, Daytime 12–18, Evening 18–24, Night 00–06.</desc>'
        '<rect x="0.5" y="0.5" width="599" height="245" rx="9" fill="#22292f" stroke="#3d444d"/>'
        '<rect x="24" y="73" width="552" height="133" rx="7" fill="#272e37"/>'
        '<g fill="none" stroke="#8b949e" stroke-width="2"><rect x="24" y="27" width="20" height="20" rx="2"/><path d="m32 33-4 4 4 4m5-8 4 4-4 4"/></g>'
        f'<text x="56" y="45" fill="#4493f8" font-family="Segoe UI, sans-serif" font-size="19" font-weight="600">{escape(title)}</text>'
        f'<g transform="translate({184 if early else 234},38)">{bird}</g>'
        '<g fill="#e6edf3" font-family="Consolas, DejaVu Sans Mono, monospace" font-size="13" xml:space="preserve">'
        + "".join(rows)
        + '</g>'
        f'<text x="25" y="229" fill="#8b949e" font-family="Segoe UI, sans-serif" font-size="11">Latest {total:,} indexed public commits · UTC+8</text>'
        '</svg>\n'
    )


if __name__ == "__main__":
    counts = collect_counts()
    target = Path(__file__).resolve().parents[1] / "assets" / "commit-time.svg"
    target.parent.mkdir(exist_ok=True)
    target.write_text(render(counts), encoding="utf-8")
    print(f"Generated card: {sum(counts)} public commits; buckets={counts}; UTC+8")
