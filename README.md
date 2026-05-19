# Scrapling API

A Python + Flask REST API that accepts a sequential list of scraping commands,
executes them in order using [Scrapling](https://scrapling.readthedocs.io/), and
returns the combined results — with Redis caching and MongoDB persistence.

## Quick Start (Docker)

```bash
# 1. Clone / enter the project directory
cd scrapling-api

# 2. Copy the example env file and review it
cp .env.example .env

# 3. Build and start all services (API + Redis + MongoDB)
docker compose up --build
```

The API will be available at `http://localhost:5000`.

---

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed.

| Variable                   | Default                        | Description                                                   |
|----------------------------|--------------------------------|---------------------------------------------------------------|
| `SECRET_KEY`               | `change-me-in-production`      | Flask secret key                                              |
| `FLASK_DEBUG`              | `false`                        | Enable Flask debug mode                                       |
| `FLASK_PORT`               | `5000`                         | Port exposed by the API container                             |
| `REDIS_URL`                | `redis://redis:6379/0`         | Redis connection URL                                          |
| `CACHE_TTL_SECONDS`        | `300`                          | How long to cache identical run results (seconds)             |
| `CACHE_ENABLED`            | `true`                         | Toggle Redis caching globally                                 |
| `MONGO_URI`                | `mongodb://mongo:27017`        | MongoDB connection URI                                        |
| `MONGO_DB`                 | `scrapling_api`                | MongoDB database name                                         |
| `PERSIST_ENABLED`          | `true`                         | Toggle MongoDB run persistence globally                       |
| `MAX_COMMANDS`             | `20`                           | Maximum commands allowed per run request                      |
| `MAX_OUTPUT_LENGTH`        | `50000`                        | Maximum characters per command output before truncation       |
| `DEFAULT_TIMEOUT_SECONDS`  | `30`                           | Default HTTP request timeout in seconds                       |
| `DEFAULT_BROWSER_TIMEOUT_MS` | `30000`                      | Default browser command timeout in milliseconds               |
| `ALLOWED_HOSTS`            | *(empty = allow all)*          | Comma-separated allowlist of scrape-able hostnames            |
| `BLOCKED_HOSTS`            | *(empty)*                      | Comma-separated blocklist — always enforced                   |

---

## API Endpoints

Full machine-readable documentation is available at `GET /api/v1/docs`
(returns the `docs/openapi.yaml` file).

### `GET /health`

Returns the health status of the API and its dependencies.

```bash
curl http://localhost:5000/health
```

```json
{
  "status": "ok",
  "dependencies": {
    "redis":   { "status": "ok" },
    "mongodb": { "status": "ok" }
  }
}
```

---

### `POST /api/v1/runs`

Execute a command workflow and return ordered results.

**Request body**

```json
{
  "commands": [ <command>, ... ],
  "cache":   true,
  "persist": true
}
```

**`cache`** (bool, default `true`) — return a cached result if an identical
request was made within the TTL window; cache successful results.

**`persist`** (bool, default `true`) — store the run record in MongoDB.

#### Command types

All commands require a `"type"` field that acts as the discriminator.

##### `get` — plain HTTP GET

```json
{
  "type": "get",
  "url": "https://example.com",
  "css_selector": "h1",
  "headers": { "Accept-Language": "en-US" },
  "cookies": "session=abc123",
  "timeout": 30,
  "impersonate": "chrome",
  "stealthy_headers": true,
  "follow_redirects": true,
  "verify_ssl": true,
  "proxy": "http://proxy:8080"
}
```

##### `post` — plain HTTP POST

```json
{
  "type": "post",
  "url": "https://api.example.com/search",
  "json_body": { "q": "scrapling" },
  "timeout": 30
}
```

##### `fetch` — browser automation (DynamicFetcher)

```json
{
  "type": "fetch",
  "url": "https://spa-app.example.com",
  "headless": true,
  "network_idle": true,
  "disable_resources": true,
  "timeout": 30000,
  "wait_selector": ".results-loaded",
  "block_ads": true
}
```

##### `stealthy_fetch` — anti-bot stealth browser (StealthyFetcher)

```json
{
  "type": "stealthy_fetch",
  "url": "https://protected.example.com",
  "solve_cloudflare": true,
  "headless": true,
  "block_webrtc": true
}
```

##### `extract` — select content from the current page

```json
{
  "type": "extract",
  "css_selector": ".article h2",
  "limit": 10
}
```

```json
{
  "type": "extract",
  "xpath": "//p[@class='summary']/text()",
  "first_only": true
}
```

To extract an attribute instead of text:

```json
{
  "type": "extract",
  "css_selector": "a.product-link",
  "attribute": "href"
}
```

##### `follow` — follow a link from the current page

```json
{
  "type": "follow",
  "css_selector": "a.next-page",
  "attribute": "href",
  "network_idle": true
}
```

##### `interact` — navigate and perform interactive browser actions

Opens a Chromium browser, navigates to `url`, executes each step in `actions`
sequentially, then stores the resulting page in context for subsequent `extract`
commands.

```json
{
  "type": "interact",
  "url": "https://example.com/login",
  "headless": true,
  "timeout": 30000,
  "css_selector": ".dashboard-title",
  "actions": [
    { "action": "hover",              "selector": "[href='#login']" },
    { "action": "fill",               "selector": "#username",          "value": "alice" },
    { "action": "fill",               "selector": "input[type=password]", "value": "secret" },
    { "action": "click",              "selector": "button[type=submit]" },
    { "action": "wait_for_load_state", "state": "networkidle" },
    { "action": "wait_for_selector",   "selector": ".dashboard" }
  ]
}
```

Supported `action` values:

| Action | Required fields | Description |
|---|---|---|
| `fill` | `selector`, `value` | Type text into an input field |
| `click` | `selector` | Click an element; waits for `domcontentloaded` after |
| `hover` | `selector` | Move the mouse over an element |
| `press` | `selector`, `value` | Press a key (e.g. `"Enter"`) on a focused element |
| `wait_for_selector` | `selector` | Pause until the selector appears in the DOM |
| `wait_for_load_state` | `state` | Pause until `"load"`, `"domcontentloaded"`, or `"networkidle"` |

Each action accepts an optional `timeout` (ms, `100`–`120000`) that overrides
the command-level `timeout` for that step only.

---

#### Example: GET + extract headings

```bash
curl -s -X POST http://localhost:5000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "commands": [
      { "type": "get",     "url": "https://quotes.toscrape.com/" },
      { "type": "extract", "css_selector": ".quote .text", "limit": 5 }
    ]
  }'
```

#### Example: browser fetch of a dynamic page

```bash
curl -s -X POST http://localhost:5000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "commands": [
      {
        "type": "fetch",
        "url": "https://quotes.toscrape.com/js/",
        "network_idle": true,
        "disable_resources": true
      },
      { "type": "extract", "css_selector": ".quote .text", "limit": 5 }
    ],
    "cache": false
  }'
```

#### Example: Cloudflare bypass (authorized sites only)

```bash
curl -s -X POST http://localhost:5000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "commands": [
      {
        "type": "stealthy_fetch",
        "url": "https://nopecha.com/demo/cloudflare",
        "solve_cloudflare": true,
        "css_selector": "#padded_content a"
      }
    ]
  }'
```

#### Example: login form with browser interaction

```bash
curl -s -X POST http://localhost:5000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "cache": false,
    "commands": [
      {
        "type": "interact",
        "url": "https://example.com/login",
        "headless": true,
        "actions": [
          { "action": "hover",  "selector": "[href=\"#login\"]" },
          { "action": "fill",   "selector": "input[name=login]",    "value": "alice" },
          { "action": "fill",   "selector": "input[type=password]", "value": "secret" },
          { "action": "click",  "selector": "button[type=submit]" },
          { "action": "wait_for_load_state", "state": "networkidle" }
        ]
      },
      { "type": "extract", "css_selector": ".user-data .activity div:first-child .num" },
      { "type": "extract", "css_selector": ".user-data .activity div:nth-of-type(2) .num" }
    ]
  }'
```

---

**Response** (`200 OK` on success, `422` on workflow error)

```json
{
  "run_id":            "6647f9abcde123456789abcd",
  "status":            "ok",
  "cache_hit":         false,
  "commands_executed": 2,
  "duration_ms":       312.5,
  "final_output":      ["Quote one", "Quote two", "..."],
  "results": [
    {
      "index":       0,
      "type":        "get",
      "status":      "ok",
      "duration_ms": 250.1,
      "output":      "<html>..."
    },
    {
      "index":       1,
      "type":        "extract",
      "status":      "ok",
      "duration_ms": 0.4,
      "output":      ["Quote one", "Quote two", "..."]
    }
  ]
}
```

---

### `GET /api/v1/runs/{run_id}`

Retrieve a previously persisted run from MongoDB.

```bash
curl http://localhost:5000/api/v1/runs/6647f9abcde123456789abcd
```

Returns the same shape as `POST /api/v1/runs` plus a `commands` array (the
original request payload) and a `created_at` ISO timestamp.

---

### `GET /api/v1/docs`

Returns the raw `docs/openapi.yaml` file.

---

## Local Development (without Docker)

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # macOS/Linux

pip install -r requirements.txt
scrapling install --force        # installs browser drivers

cp .env.example .env
# edit .env — point REDIS_URL and MONGO_URI at local instances

python wsgi.py
```

Run tests:

```bash
pytest tests/ -v
```

---

## Security Guardrails

- Only `http` and `https` URL schemes are accepted.
- Private/internal IPs are rejected by Scrapling's default redirect safety.
- Configure `ALLOWED_HOSTS` to restrict scraping to a known set of domains.
- Configure `BLOCKED_HOSTS` to unconditionally block specific domains.
- Scrapling solver works through browser automation — no external solver APIs, no credentials required.
- Never scrape personal or sensitive data; respect robots.txt and site Terms of Service.
- For production, add authentication and rate limiting before exposing this API publicly.

---

## Architecture

```
Request
  │
  ▼
Flask (routes.py)
  │
  ├── Pydantic validation (schemas.py)
  │
  ├── Redis cache lookup (cache.py)
  │       └── cache hit → return immediately
  │
  ├── Runner (runner.py)
  │       └── command[0] → Scrapling Fetcher / DynamicFetcher / StealthyFetcher
  │           command[1] → extract / follow / ...
  │           ...
  │
  ├── MongoDB persistence (store.py)
  │
  └── Redis cache write
```

Services in `docker-compose.yml`:

| Service  | Image          | Port  |
|----------|----------------|-------|
| `api`    | (built locally)| 5000  |
| `redis`  | redis:7-alpine | —     |
| `mongo`  | mongo:7        | —     |
