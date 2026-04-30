# Jupiter Token Radar

A CLI tool that cross-references Jupiter's **Token API** (trending + organic score) with the **Price API** to surface genuinely active Solana tokens and flag suspicious ones.

Built with [Claude Code](https://claude.ai/code) using [Jupiter Agent Skills](https://github.com/jup-ag/agent-skills) as context.

---

## What it does

- Fetches top trending tokens from Jupiter Token API (`/tokens/v2/toptrending/{interval}`)
- Enriches each token with real-time USD prices from Price API (`/price/v3`)
- Computes a **risk assessment** per token using:
  - `organicScore` — ratio of real vs bot trading activity
  - `audit.mintAuthorityDisabled` / `audit.freezeAuthorityDisabled`
  - holder count
- Outputs a ranked table or JSON report

The novel combination: **trending rank × organic score × audit flags** in a single view. Jupiter's APIs return all this data but don't combine it out of the box.

---

## Quick start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your API key (from developers.jup.ag/portal)
export JUPITER_API_KEY=jup_...

# Run
python radar.py
```

---

## Usage

```
python radar.py [options]

Options:
  --interval    5m | 1h | 6h | 24h   trending window (default: 1h)
  --limit       N                     tokens to fetch (default: 30)
  --min-score   N                     hide tokens with organic score < N
  --risky-only                        show only HIGH / MED risk tokens
  --watch       SECONDS               poll continuously
  --json                              output as JSON
```

### Examples

```bash
# Top 20 tokens trending in last hour, hide low-score tokens
python radar.py --interval 1h --limit 20 --min-score 60

# Only show suspicious/risky tokens from 24h trending
python radar.py --interval 24h --risky-only

# Auto-refresh every 60 seconds
python radar.py --interval 5m --watch 60

# JSON output for scripting
python radar.py --interval 1h --json > report.json
```

---

## Sample output

```
================================================================================
  Jupiter Token Radar  |  trending/1h  |  2026-04-30 00:03 UTC
  organic_score ≥ 0  |  20 tokens scanned
================================================================================
  Symbol            Price   Change      Org.Score   Holders Status   Flags
  ---------- ------------ -------- -------------- --------- -------- --------------------
  ✓JUP            $0.1819    +0.9%    97.6 (high)   846,300 ✓ safe   -
  ✓ASTEROID     $0.003453   +14.2%    77.5 (medi)     4,615 ✓ safe   -
   OTTO         $0.000053  +388.7%      0.0 (low)       151 ✗ risky  LOW_ORGANIC, BOT_ACTIVITY
```

---

## Risk flags

| Flag | Meaning |
|------|---------|
| `MINT_OPEN` | Token mint authority not disabled — supply can be inflated |
| `FREEZE_OPEN` | Freeze authority not disabled — accounts can be frozen |
| `LOW_ORGANIC` | Organic score < 30 — trading dominated by bots |
| `MED_ORGANIC` | Organic score 30–60 — mixed signal |
| `BOT_ACTIVITY` | Jupiter labels this token as low organic activity |
| `FEW_HOLDERS` | Fewer than 200 holders — concentrated ownership |

Severity: **HIGH** = any of MINT_OPEN, LOW_ORGANIC, BOT_ACTIVITY · **MED** = other flags · **OK** = clean

---

## APIs used

| API | Endpoint | Purpose |
|-----|----------|---------|
| Token API v2 | `GET /tokens/v2/toptrending/{interval}` | Trending tokens + organic score + audit |
| Price API v3 | `GET /price/v3?ids={mints}` | Real-time USD prices (up to 50/request) |

Built following the [`integrating-jupiter`](https://github.com/jup-ag/agent-skills) Agent Skill — get your API key at [developers.jup.ag/portal](https://developers.jup.ag/portal).

---

## Notes

- Without `JUPITER_API_KEY`: falls back to keyless (0.5 RPS)
- Rate limit handling: automatic exponential backoff on 429
- Prices failing silently (null) are shown as `N/A` — Jupiter's documented behavior for low-liquidity tokens
