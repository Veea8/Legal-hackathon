# Apertus access (Swisscom, Swiss AI Weeks)

Source: https://zh.ai-weeks.ch/tools/swisscom-hacker-guide

| Item | Value |
|---|---|
| Base URL | `https://api.swisscom.com/products/swiss-ai-weeks/apertus-1.5-70b/v1` |
| Model id | `swiss-ai/Apertus-v1.5-70B` |
| Auth | `Authorization: Bearer <key>` — the key is used directly, no OAuth exchange |
| Key source | "The Keymaker" portal → select Swisscom → the email you registered with on Luma → key arrives by mail |
| Rate limit | 5 requests/s → we run at most 4 concurrent calls and ≤ 4 req/s (`AI_CONCURRENCY`, `AI_MAX_RPS`) |
| Budgets | 10,000,000 input tokens, 2,500,000 output tokens per key. One eval run over the 29 fields ≈ 45k in / 9k out |
| Context | up to 262,144 tokens; streaming supported |
| Caveat | The guide says "Authorization Bearer expires in 60 minutes". It is unclear whether the key itself expires. `scripts/benchmark_apertus.py` checks this at the start of the day. If keys really expire hourly: re-issue via the Keymaker mail and update `.env`; the client re-reads the key on a 401 without a restart. |

## Usage (OpenAI-compatible)

```python
from openai import OpenAI
client = OpenAI(api_key=os.environ["APERTUS_API_KEY"], base_url=os.environ["APERTUS_BASE_URL"])
r = client.chat.completions.create(model=os.environ["APERTUS_MODEL"], messages=[...], temperature=0.2)
```

## Fallback provider: PublicAI

| Item | Value |
|---|---|
| Base URL | `https://api.publicai.co/v1` |
| Model id | `swiss-ai/apertus-v1.5-70b` (also `swiss-ai/apertus-70b-instruct`, `swiss-ai/apertus-8b-instruct`) |
| Auth | `Authorization: Bearer <key>`; a `User-Agent` header is required |
| Rate limit | Free tier 100 requests/min |
| Notes | JSON mode undocumented; the client already tolerates plain-text JSON |

Switching provider = changing `APERTUS_BASE_URL`, `APERTUS_API_KEY`, `APERTUS_MODEL` in `backend/.env`.

## Rules

- `backend/.env` is gitignored. Never commit the key. `/api/health` only reports "key set / not set".
- Keep prompts short: the KB goes in as one line per entry, sibling fields as one line each.
- If p50 latency per field call is above 15 s on the 70B, try the 8B on PublicAI and re-run `scripts/eval.py`.
