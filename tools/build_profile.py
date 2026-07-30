#!/usr/bin/env python3
"""
build_profile.py - generate the SVG cards used by the profile README.

Everything the README shows is rendered here and committed into this repository,
so the images are served by GitHub itself. No third-party card service is in the
path, which is the whole point: those rate-limit and the README ends up showing
broken-image icons.

Data comes from the GitHub GraphQL API through `gh`, authenticated as the profile
owner, so private-repository contributions are included in the totals.

Two files are written per card, a dark and a light variant, because a README
switches themes with <picture><source media="(prefers-color-scheme: dark)">.

    python tools/build_profile.py
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"

ACCENT = "#39D353"

THEMES = {
    "dark": {
        "bg": "#0d1117", "panel": "#161b22", "border": "#30363d",
        "text": "#e6edf3", "dim": "#8b949e", "grid": "#21262d",
    },
    "light": {
        "bg": "#ffffff", "panel": "#f6f8fa", "border": "#d0d7de",
        "text": "#1f2328", "dim": "#59636e", "grid": "#eaeef2",
    },
}

LANG_COLORS = {
    "Python": "#3572A5", "Java": "#b07219", "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6", "HTML": "#e34c26", "CSS": "#563d7c",
    "Lua": "#000080", "Shell": "#89e051", "C": "#555555", "C++": "#f34b7d",
    "C#": "#178600", "Go": "#00ADD8", "Rust": "#dea584", "Ruby": "#701516",
    "PHP": "#4F5D95", "Kotlin": "#A97BFF", "Swift": "#F05138",
    "PowerShell": "#012456", "Dockerfile": "#384d54", "Makefile": "#427819",
    "Jupyter Notebook": "#DA5B0B", "Vue": "#41b883", "SCSS": "#c6538c",
}

FONT = "-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif"


def gh_graphql(query: str) -> dict:
    out = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}"],
        capture_output=True, text=True, check=True, encoding="utf-8",
    )
    return json.loads(out.stdout)["data"]


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# --------------------------------------------------------------------------- data

def fetch() -> dict:
    today = dt.date.today()
    start = today - dt.timedelta(days=364)

    q = """
    {
      viewer {
        login
        name
        followers { totalCount }
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          totalCount
          nodes {
            name
            isPrivate
            stargazerCount
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name } }
            }
          }
        }
        contributionsCollection(from: "%sT00:00:00Z", to: "%sT23:59:59Z") {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          restrictedContributionsCount
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }
    """ % (start.isoformat(), today.isoformat())

    v = gh_graphql(q)["viewer"]
    cc = v["contributionsCollection"]

    days = []
    for w in cc["contributionCalendar"]["weeks"]:
        for d in w["contributionDays"]:
            days.append((dt.date.fromisoformat(d["date"]), d["contributionCount"]))
    days.sort()

    langs: dict[str, int] = {}
    stars = 0
    for r in v["repositories"]["nodes"]:
        stars += r["stargazerCount"]
        for e in r["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]

    return {
        "login": v["login"],
        "name": v["name"] or v["login"],
        "followers": v["followers"]["totalCount"],
        "repos": v["repositories"]["totalCount"],
        "stars": stars,
        "total": cc["contributionCalendar"]["totalContributions"],
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "days": days,
        "langs": dict(sorted(langs.items(), key=lambda kv: -kv[1])),
    }


def streaks(days: list[tuple[dt.date, int]]) -> tuple[int, int]:
    """Current streak (today may still be empty) and longest streak in the window."""
    longest = run = 0
    for _, n in days:
        run = run + 1 if n > 0 else 0
        longest = max(longest, run)

    current = 0
    for d, n in reversed(days):
        if n > 0:
            current += 1
        elif d == days[-1][0]:
            continue          # today not started yet - does not break the streak
        else:
            break
    return current, longest


# --------------------------------------------------------------------------- cards

def card_stats(data: dict, theme: str) -> str:
    t = THEMES[theme]
    W, H = 500, 235
    cur, longest = streaks(data["days"])

    # weekly totals for the last 26 weeks
    weeks: list[int] = []
    chunk = data["days"][-26 * 7:]
    for i in range(0, len(chunk), 7):
        weeks.append(sum(n for _, n in chunk[i:i + 7]))
    peak = max(weeks) or 1

    bar_w, gap = 13, 4
    chart_x, chart_y, chart_h = 26, 150, 52
    bars = []
    for i, v in enumerate(weeks):
        h = max(2, round(chart_h * v / peak))
        x = chart_x + i * (bar_w + gap)
        y = chart_y + chart_h - h
        op = 0.35 + 0.65 * (v / peak)
        bars.append(
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" rx="2.5" '
            f'fill="{ACCENT}" opacity="{op:.2f}"/>'
        )

    def stat(x: int, value: str, label: str) -> str:
        return (
            f'<text x="{x}" y="98" font-family="{FONT}" font-size="30" font-weight="700" '
            f'fill="{t["text"]}" text-anchor="middle">{esc(value)}</text>'
            f'<text x="{x}" y="118" font-family="{FONT}" font-size="11" '
            f'fill="{t["dim"]}" text-anchor="middle">{esc(label)}</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub activity">
  <rect width="{W}" height="{H}" rx="10" fill="{t['panel']}" stroke="{t['border']}"/>
  <text x="26" y="38" font-family="{FONT}" font-size="15" font-weight="600" fill="{ACCENT}">GitHub activity</text>
  <text x="26" y="56" font-family="{FONT}" font-size="11" fill="{t['dim']}">last 12 months, private contributions included</text>
  {stat(90, str(data['total']), 'contributions')}
  {stat(215, str(cur), 'day streak')}
  {stat(340, str(longest), 'longest streak')}
  {stat(452, str(data['repos']), 'repositories')}
  <text x="26" y="143" font-family="{FONT}" font-size="10" fill="{t['dim']}">WEEKLY, LAST 26 WEEKS</text>
  <line x1="26" y1="{chart_y + chart_h + 6}" x2="{W - 26}" y2="{chart_y + chart_h + 6}" stroke="{t['grid']}"/>
  {''.join(bars)}
</svg>"""


def card_langs(data: dict, theme: str, top: int = 6) -> str:
    t = THEMES[theme]
    W = 380
    items = list(data["langs"].items())[:top]
    total = sum(v for _, v in items) or 1
    H = 92 + len(items) * 26

    rows = []
    y = 78
    for name, size in items:
        pct = 100 * size / total
        colour = LANG_COLORS.get(name, ACCENT)
        bar_w = round(200 * size / total)
        rows.append(
            f'<circle cx="30" cy="{y - 4}" r="5" fill="{colour}"/>'
            f'<text x="45" y="{y}" font-family="{FONT}" font-size="12.5" fill="{t["text"]}">{esc(name)}</text>'
            f'<rect x="150" y="{y - 11}" width="200" height="8" rx="4" fill="{t["grid"]}"/>'
            f'<rect x="150" y="{y - 11}" width="{bar_w}" height="8" rx="4" fill="{colour}"/>'
            f'<text x="{W - 26}" y="{y}" font-family="{FONT}" font-size="11" fill="{t["dim"]}" '
            f'text-anchor="end">{pct:.1f}%</text>'
        )
        y += 26

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Most used languages">
  <rect width="{W}" height="{H}" rx="10" fill="{t['panel']}" stroke="{t['border']}"/>
  <text x="26" y="38" font-family="{FONT}" font-size="15" font-weight="600" fill="{ACCENT}">Most used languages</text>
  <text x="26" y="56" font-family="{FONT}" font-size="11" fill="{t['dim']}">by bytes of code across my repositories</text>
  {''.join(rows)}
</svg>"""


def card_header(data: dict, theme: str) -> str:
    t = THEMES[theme]
    W, H = 880, 150
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(data['name'])}">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{ACCENT}" stop-opacity="0.16"/>
      <stop offset="55%" stop-color="{ACCENT}" stop-opacity="0.05"/>
      <stop offset="100%" stop-color="{t['panel']}" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" rx="12" fill="{t['panel']}" stroke="{t['border']}"/>
  <rect width="{W}" height="{H}" rx="12" fill="url(#g)"/>
  <rect x="0" y="0" width="4" height="{H}" rx="2" fill="{ACCENT}"/>
  <text x="40" y="58" font-family="{FONT}" font-size="30" font-weight="700" fill="{t['text']}">{esc(data['name'])}</text>
  <text x="40" y="88" font-family="{FONT}" font-size="15" fill="{ACCENT}">Cybersecurity student at SETU</text>
  <text x="40" y="115" font-family="{FONT}" font-size="13" fill="{t['dim']}">Security, networking and reverse engineering &#183; always building something on the side.</text>
</svg>"""


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    print("querying github...")
    data = fetch()
    cur, longest = streaks(data["days"])
    print(f"  {data['total']} contributions, streak {cur}, longest {longest}, "
          f"{data['repos']} repos, {len(data['langs'])} languages")

    for theme in THEMES:
        (ASSETS / f"header-{theme}.svg").write_text(card_header(data, theme), encoding="utf-8")
        (ASSETS / f"stats-{theme}.svg").write_text(card_stats(data, theme), encoding="utf-8")
        (ASSETS / f"langs-{theme}.svg").write_text(card_langs(data, theme), encoding="utf-8")
    print(f"wrote 6 svg files to {ASSETS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
