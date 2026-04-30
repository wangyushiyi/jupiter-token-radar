#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jupiter Token Radar
Combines Jupiter Token API (trending + organic score) with Price API
to surface genuinely active tokens and flag suspicious ones.
"""

import os
import sys
import time
import json
import argparse
import requests
from datetime import datetime, timezone

API_KEY = os.environ.get("JUPITER_API_KEY", "")
BASE    = "https://api.jup.ag"
HEADERS = {"x-api-key": API_KEY} if API_KEY else {}

# ── HTTP helpers ────────────────────────────────────────────────────────────

def jup_get(path: str, params: dict = None) -> dict | list:
    url = f"{BASE}{path}"
    for attempt in range(3):
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 10))
            print(f"  [rate limit] waiting {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Failed after retries: {path}")

# ── Data fetching ────────────────────────────────────────────────────────────

def fetch_trending(interval: str = "1h", limit: int = 20) -> list[dict]:
    """Top trending tokens by interval (5m / 1h / 6h / 24h)."""
    data = jup_get(f"/tokens/v2/toptrending/{interval}")
    return data[:limit] if isinstance(data, list) else []

def fetch_prices(mints: list[str]) -> dict[str, dict]:
    """Batch price lookup — max 50 mints per call."""
    if not mints:
        return {}
    chunks = [mints[i:i+50] for i in range(0, len(mints), 50)]
    result = {}
    for chunk in chunks:
        data = jup_get("/price/v3", params={"ids": ",".join(chunk)})
        result.update(data if isinstance(data, dict) else {})
    return result

def fetch_token_details(mints: list[str]) -> dict[str, dict]:
    """Fetch full token metadata for a list of mints."""
    if not mints:
        return {}
    result = {}
    # Token API search by mint (comma-separated, max 100)
    chunks = [mints[i:i+100] for i in range(0, len(mints), 100)]
    for chunk in chunks:
        data = jup_get("/tokens/v2/search", params={"query": ",".join(chunk)})
        if isinstance(data, list):
            for t in data:
                result[t["id"]] = t
    return result

# ── Analysis ─────────────────────────────────────────────────────────────────

def risk_flags(token: dict) -> list[str]:
    flags = []
    audit = token.get("audit", {})
    if not audit.get("mintAuthorityDisabled"):
        flags.append("MINT_OPEN")
    if not audit.get("freezeAuthorityDisabled"):
        flags.append("FREEZE_OPEN")
    score = token.get("organicScore", 0)
    if score < 30:
        flags.append("LOW_ORGANIC")
    elif score < 60:
        flags.append("MED_ORGANIC")
    if token.get("organicScoreLabel") == "low":
        flags.append("BOT_ACTIVITY")
    holders = token.get("holderCount", 0)
    if holders and holders < 200:
        flags.append("FEW_HOLDERS")
    return flags

def severity(flags: list[str]) -> str:
    high = {"MINT_OPEN", "LOW_ORGANIC", "BOT_ACTIVITY"}
    if any(f in high for f in flags):
        return "HIGH"
    if flags:
        return "MED"
    return "OK"

# ── Output ────────────────────────────────────────────────────────────────────

SEV_ICON = {"OK": "✓", "MED": "⚠", "HIGH": "✗"}
SEV_LABEL = {"OK": "safe", "MED": "caution", "HIGH": "risky"}

def fmt_price(p) -> str:
    if p is None:
        return "N/A"
    price = float(p.get("usdPrice") or p.get("price") or 0)
    if price == 0:
        return "$0"
    if price < 0.000001:
        return f"${price:.2e}"
    if price < 0.01:
        return f"${price:.6f}"
    if price < 1:
        return f"${price:.4f}"
    return f"${price:,.2f}"

def fmt_change(token: dict, interval: str) -> str:
    stats_key = {
        "5m": "stats5m", "1h": "stats1h",
        "6h": "stats6h", "24h": "stats24h"
    }.get(interval, "stats1h")
    stats = token.get(stats_key, {})
    chg = stats.get("priceChange")
    if chg is None:
        return "  N/A "
    sign = "+" if chg >= 0 else ""
    return f"{sign}{chg:.1f}%"

def fmt_score(token: dict) -> str:
    score = token.get("organicScore")
    label = token.get("organicScoreLabel", "")
    if score is None:
        return "  N/A"
    return f"{score:5.1f} ({label[:4]})"

def print_report(tokens: list[dict], prices: dict, interval: str, min_score: float):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*80}")
    print(f"  Jupiter Token Radar  |  trending/{interval}  |  {ts}")
    print(f"  organic_score ≥ {min_score}  |  {len(tokens)} tokens scanned")
    print(f"{'='*80}")
    print(f"  {'Symbol':<10} {'Price':>12} {'Change':>8} {'Org.Score':>14} {'Holders':>9} {'Status':<8} {'Flags'}")
    print(f"  {'-'*10} {'-'*12} {'-'*8} {'-'*14} {'-'*9} {'-'*8} {'-'*20}")

    shown = filtered = 0
    for t in tokens:
        score = t.get("organicScore", 0) or 0
        if score < min_score:
            filtered += 1
            continue

        mint    = t["id"]
        symbol  = t.get("symbol", mint[:8])[:10]
        price   = prices.get(mint)
        flags   = risk_flags(t)
        sev     = severity(flags)
        icon    = SEV_ICON[sev]
        chg     = fmt_change(t, interval)
        holders = t.get("holderCount", 0) or 0
        verified = "✓" if t.get("isVerified") else " "

        print(f"  {verified}{symbol:<9} {fmt_price(price):>12} {chg:>8} "
              f"{fmt_score(t):>14} {holders:>9,} {icon+' '+SEV_LABEL[sev]:<8} "
              f"{', '.join(flags) or '-'}")
        shown += 1

    print(f"{'='*80}")
    print(f"  Shown: {shown}  |  Filtered (score < {min_score}): {filtered}")

def print_json(tokens: list[dict], prices: dict, interval: str):
    out = []
    for t in tokens:
        mint = t["id"]
        out.append({
            "mint":         mint,
            "symbol":       t.get("symbol"),
            "name":         t.get("name"),
            "usdPrice":     (prices.get(mint) or {}).get("usdPrice"),
            "priceChange":  (t.get("stats1h") or {}).get("priceChange"),
            "organicScore": t.get("organicScore"),
            "organicLabel": t.get("organicScoreLabel"),
            "isVerified":   t.get("isVerified"),
            "holderCount":  t.get("holderCount"),
            "riskFlags":    risk_flags(t),
            "severity":     severity(risk_flags(t)),
        })
    print(json.dumps(out, indent=2))

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Jupiter Token Radar — surfaces trending Solana tokens with real organic activity"
    )
    parser.add_argument("--interval",  default="1h",
                        choices=["5m", "1h", "6h", "24h"],
                        help="trending interval (default: 1h)")
    parser.add_argument("--limit",     type=int, default=30,
                        help="max tokens to fetch (default: 30)")
    parser.add_argument("--min-score", type=float, default=0,
                        help="hide tokens below this organic score (default: 0 = show all)")
    parser.add_argument("--watch",     type=int, metavar="SECONDS",
                        help="poll continuously every N seconds")
    parser.add_argument("--json",      action="store_true",
                        help="output as JSON instead of table")
    parser.add_argument("--risky-only", action="store_true",
                        help="show only HIGH/MED risk tokens")
    args = parser.parse_args()

    if not API_KEY:
        print("Warning: JUPITER_API_KEY not set, using keyless (0.5 RPS)", file=sys.stderr)

    def run_once():
        tokens = fetch_trending(args.interval, args.limit)
        if not tokens:
            print("No trending tokens returned.", file=sys.stderr)
            return
        mints  = [t["id"] for t in tokens]
        prices = fetch_prices(mints)

        if args.risky_only:
            tokens = [t for t in tokens if severity(risk_flags(t)) in ("HIGH", "MED")]

        if args.json:
            print_json(tokens, prices, args.interval)
        else:
            print_report(tokens, prices, args.interval, args.min_score)

    if args.watch:
        while True:
            run_once()
            print(f"\n  [next refresh in {args.watch}s — Ctrl+C to stop]")
            time.sleep(args.watch)
    else:
        run_once()

if __name__ == "__main__":
    main()
