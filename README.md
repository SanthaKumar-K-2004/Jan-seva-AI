# Jan-Seva AI
"Find the Unknown. Serve the Unserved. Charge Nothing."

API-first AI assistant for Indian government scheme discovery, eligibility guidance, and application support.

## Quick Start
1. Setup
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Fill API keys in .env (never hardcode keys in code)
```

2. Run
```bash
cd backend
python -m app.main
```

3. Docs
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Enterprise Quality Features
- Multi-key LLM failover:
  - Groq (`GROQ_API_KEY`, `_2`, `_3`)
  - Gemini (`GOOGLE_API_KEY`, `_2`, `_3`)
  - OpenAI (`OPENAI_API_KEY`, `_2`, `_3`, optional CSV list)
- Adaptive token fallback for OpenAI calls.
- Strict source verification controls:
  - Domain reliability threshold
  - Source recency filters
  - Multi-source verification flag for latest-news intent
- Persistent research cache (SQLite) for faster repeat queries with TTL.
- Source metadata returned per citation:
  - URL, domain, score, reliability, publish date, verified flag

## Key Environment Flags
- `STRICT_VERIFIED_MODE=true`
- `MIN_SOURCE_RELIABILITY=0.67`
- `MAX_SOURCE_AGE_DAYS=45`
- `MAX_NEWS_AGE_DAYS=21`
- `REQUIRE_MULTI_SOURCE_FOR_NEWS=true`
- `RESEARCH_CACHE_ENABLED=true`
- `RESEARCH_CACHE_TTL_MINUTES=180`
- `RESEARCH_CACHE_PATH=data/research_cache.sqlite3`

## Security Note
- If an API key is exposed in chat, logs, or commits, rotate/revoke it immediately and replace it in `.env`.
