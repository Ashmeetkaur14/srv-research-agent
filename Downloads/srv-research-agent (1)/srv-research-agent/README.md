# SRVCABLE Research Agent — Super Investing assignment (Part B)

Takes an NSE ticker + a folder of scraped documents and writes a one-page, source-cited research brief.

## Run (Windows)
```powershell
py -m pip install -r requirements.txt
# put the 8 research-pack files in data/research_pack/
powershell -ExecutionPolicy Bypass -File .\run.ps1 -Mode pipeline -Note "what I changed"
```
`run.ps1` asks for your Gemini API key (free tier from Google AI Studio) and does not store it.
Or manually: `$env:GEMINI_API_KEY="..."; py -m research_agent --mode pipeline --note "..."` (macOS/Linux: `export GEMINI_API_KEY=...; python -m research_agent ...`).

Each run is saved in `runs/<time>/`: `brief.md`, `trace.json` (every intermediate step, including excluded documents), `meta.json`, and the exact prompts used.
`--mode single` is the baseline (one prompt, no checks) used to compare against the pipeline.

## How the agent thinks
0. **Code pre-checks (no LLM):** parse each header (source / url / date / type), compute document age against today (23 Sep 2026),
   and scan for text aimed at an AI ("ignore previous instructions", hidden HTML comments). Such documents are excluded as evidence.
1. **Extract** — each document is read alone; the model returns claims, each with an *exact quote*, plus the entity it describes.
   Code verifies the quote really exists in the document; claims with invented evidence are dropped.
2. **Reconcile** — compares claims across documents: wrong-entity documents (similar company name, different business), conflicts
   (with an arithmetic consistency test, e.g. does margin = EBITDA ÷ revenue?), superseded/stale data, repeated-not-independent sources.
3. **Exclude (code)** — wrong-entity and injection-flagged documents are removed before the writer sees any of their claims.
4. **Write** — only from usable claims; every factual sentence gets a `[S#]` tag; derived numbers are labelled with their inputs.
5. **Check** — code verifies tags exist and numbers are cited; a second LLM pass fact-checks the draft. If issues are found, it rewrites once.
6. **Sources** — built by code from the document headers, so it cannot be hallucinated.

Documents are treated as untrusted data. See `prompts/system.md` (the system prompt).

## Models
Any of: Claude (`claude-sonnet-5-5`, default for Anthropic) or Gemini (`gemini-2.5-flash`, default for Gemini; has a free tier). Override with `LLM_MODEL`.
<!-- EDIT: write which model YOU actually used and why, after you run it. -->

## Limitations
- Only reads text/markdown/html files. PDFs must be converted first.
- Extra LLM calls (one per document + 3) cost more time than a single prompt; this trades speed for checkability.
- The critic is itself an LLM, so it can miss errors; quote-checking is the only fully deterministic guard.

## Tests
`python -m pytest -q` (offline, uses a fake LLM).
