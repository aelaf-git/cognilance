# Web Scraper Agent

Skill: `web-scraping` · Port: `8102`

Independent `CognilanceWorker` that searches the web (DuckDuckGo, or Tavily/Serper when
API keys are present), scrapes pages with httpx + BeautifulSoup, and extracts grounded,
structured answers with Groq. Returns `summary` + `sources` (+ optional `extracted`
fields) compatible with the `research-sources` UI.

- With URL(s) in the request: fetches them directly (up to 4 pages).
- Without URLs: searches first, then scrapes the top results.

## Run

```bash
pip install -e ../../. -r requirements.txt
python agent.py
```

Requires `GROQ_API_KEY` in `agents/web_scraper/.env` and the registry on `:8088`.

Optional in `.env`: `GROQ_MODEL` (default `llama-3.3-70b-versatile`),
`TAVILY_API_KEY`, `SERPER_API_KEY` (preferred search providers when set).
