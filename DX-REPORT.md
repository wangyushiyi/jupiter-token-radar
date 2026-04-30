# Developer Experience Report — Jupiter Developer Platform

**Project:** Jupiter Token Radar  
**Builder:** shiyi ([@wangyushiyi](https://github.com/wangyushiyi))  
**Date:** 2026-04-30  
**AI Stack used:** Claude Code + Jupiter Agent Skills (`integrating-jupiter`)

---

## 1. Onboarding: time to first successful API call

**Total time: ~8 minutes.**

The path was:
1. Landed on `developers.jup.ag` → found the portal link
2. Registered at `developers.jup.ag/portal` → API key issued immediately, no approval wait
3. Ran first `GET /price/v3?ids=So111...` → got a valid JSON response

That part was genuinely fast. No email confirmation loop, no credit card, no quota request form. The key just worked.

**What slowed me down:**  
The docs site URL is `developers.jup.ag/docs` but the actual API base is `api.jup.ag`. These are two different domains. I spent about 3 minutes trying `https://developers.jup.ag/price/v3` before realizing the base URL was elsewhere. The quickstart on the portal page should show a working curl example with the full `api.jup.ag` base URL on the same screen where the key is issued — right now you get your key and then have to navigate elsewhere to find out where to use it.

---

## 2. Documentation issues

**Page: [developers.jup.ag/docs/tokens](https://developers.jup.ag/docs/tokens)**

The Token API v2 endpoint for trending tokens is `GET /tokens/v2/toptrending/{interval}`, but the docs don't prominently surface this endpoint. I only found it by reading the Agent Skills SKILL.md file (`integrating-jupiter`), which listed it in the Tokens section. The main docs page for Tokens focuses on search and metadata, and the trending/category endpoints are buried. A "What can I do with this API?" summary box at the top of each API page would help.

**Page: [developers.jup.ag/docs/price](https://developers.jup.ag/docs/price)**

The Price API v3 response format in the docs shows a `price` field, but the actual response returned `usdPrice` as the key name (not `price`). Both seem to exist depending on how the response is accessed, but the inconsistency caused a silent bug — my formatter was reading `price` and getting `None` for several tokens, showing `$0` instead of the real value. Only caught it by printing the raw response. The OpenAPI spec and the docs example should match the actual response field names exactly.

**Page: Agent Skills install process**

Running `npx skills add jup-ag/agent-skills` without the `--yes` flag drops into an interactive terminal selector that hangs in non-TTY environments (CI, Claude Code's subprocess). The `--yes` flag isn't shown in the install command on the docs page — it's only mentioned as a tip in the CLI output after you've already triggered the hang. The docs page should show `npx skills add jup-ag/agent-skills --yes` as the primary command.

---

## 3. Where the APIs surprised me

**Trending endpoint returns tokens without price data**  
`GET /tokens/v2/toptrending/1h` returned tokens that had no entry in `/price/v3`. These aren't errors — Jupiter's docs note that low-liquidity tokens may return `null` from the Price API. But when building a combined view, you get silent gaps. A `priceAvailable: bool` field on the token metadata response would let clients handle this without a second lookup.

**`organicScore` of 0 is valid, not missing**  
Token `OTTO` returned `organicScore: 0.0` with label `low`. At first I treated `0` as a missing value and filtered it out — same as `null`. But 0 is a real score meaning "entirely bot-driven." The docs don't explicitly state that 0 is a valid score value, not a null sentinel. Worth one sentence in the docs.

**JLP (Jupiter's own LP token) flags as MINT_OPEN**  
JLP has `mintAuthorityDisabled: false` in the audit object, which my tool flags as risky. This is technically correct — LP tokens need mint authority to function — but it means Jupiter's own flagship token appears "risky" in any tool that naively reads the audit field. The audit schema could include a `mintPurpose` field (e.g., `"lp-managed"`) to distinguish intentional mint authority from a red flag.

**Rate limit header is inconsistent**  
On one 429 response I received a `Retry-After` header. On another I didn't. My retry logic falls back to a 10s default when the header is absent, but it would be cleaner if the header was always present on 429.

---

## 4. AI Stack: what worked, what didn't

**What I used:** `integrating-jupiter` Agent Skill (via `npx skills add jup-ag/agent-skills --yes`)

**What worked well:**

The SKILL.md is excellent as a reference document. Having the Intent Router table (user intent → API family → first action) in a structured format that Claude Code can read as context meant I didn't have to write "how do I look up a token price" in my prompt — Claude already knew to use `/price/v3` and the `x-api-key` header pattern. The error code table for Swap API is the kind of thing that would take 30 minutes to piece together from docs; having it in the skill file saved real time.

The `examples/price.md` file was directly useful — the confidence-level filtering pattern is a non-obvious best practice that I wouldn't have added without seeing it in the example.

**What didn't work:**

The skill files cover Swap, Lend, Trigger well, but the **Tokens API trending endpoints are not in the examples directory**. There's no `examples/tokens.md`. I knew the endpoint existed from the SKILL.md table, but had to experiment with the response shape manually. An `examples/tokens.md` covering toptrending, search, and organicScore interpretation would be a direct addition.

**Docs MCP:** Did not test — would require a running MCP server setup that added friction for a quick build. If the Docs MCP had a one-line npx launcher similar to `skills`, I'd have tried it.

**Jupiter CLI:** Did not use — the project is read-only (no swaps or order execution), so the CLI wasn't in scope. For a project that executes trades it would be the right tool.

---

## 5. How I'd rebuild developers.jup.ag

The platform is functional but the journey from "I have a key" to "I shipped something" has one gap: **there's no worked example that combines two APIs**.

Every API has its own docs section, but real applications pull from multiple endpoints. The Token API and Price API are natural complements — one gives metadata and signals, the other gives current value — but there's no "combining Token + Price" guide anywhere. A "recipes" section (2–3 multi-API examples like "build a token screener", "build a price alert") would dramatically reduce the time from key issuance to a working product.

Second: the portal page that shows your API key should have a one-liner test command right next to the key:
```bash
curl "https://api.jup.ag/price/v3?ids=So11111111111111111111111111111111111111112" \
  -H "x-api-key: YOUR_KEY_HERE"
```
Most developers will copy-paste this first. Right now you have to find the docs, find the base URL, find the endpoint, and construct the request yourself. That's 4 steps instead of 1.

---

## 6. What I wish existed

**A token risk scoring endpoint**  
Something like `GET /tokens/v2/{mint}/risk` that returns a computed risk summary: organic score tier, audit flags, concentration risk, and a single composite score. Right now building a risk view requires fetching full token metadata and computing it client-side. Many builders will skip this and ship tools without surfacing bot-activity signals to users.

**Organic score history**  
`organicScore` is a snapshot. A `GET /tokens/v2/{mint}/organic-history?interval=24h` returning score over time would let tools detect wash-trading ramp-ups — a score that jumps from 20 to 80 in 2 hours is a different signal than a stable 80.

**Batch token metadata endpoint**  
`GET /tokens/v2/search?query={mint1,mint2,...}` works for batch lookups but it's documented as a search endpoint, not a batch-fetch endpoint. The response returns search results, not guaranteed per-mint resolution. A dedicated `POST /tokens/v2/batch` with a body of `{"mints": [...]}` and guaranteed per-mint responses (including explicit nulls for unknown mints) would be cleaner for applications that need to enrich a list of mints from another source.

**`--yes` flag documented on the Agent Skills install page**  
Small thing, but `npx skills add jup-ag/agent-skills --yes` should be the default command shown, not the interactive version.

---

*This report was written based on a single focused build session using Claude Code with Jupiter Agent Skills. All friction points are from actual development, not synthetic testing.*
