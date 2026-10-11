import json
import re
from datetime import date
from pathlib import Path

from . import llm

TODAY = "23 September 2026"
TODAY_DATE = date(2026, 9, 23)


def load_prompt(prompts_dir: str, name: str) -> str:
    return (Path(prompts_dir) / name).read_text(encoding="utf-8").replace("{{TODAY}}", TODAY)


def parse_json(text: str):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if m:
            return json.loads(m.group(1))
        raise


def llm_json(system, user, retries=1, **kw):
    """Ask for JSON; if parsing fails, retry once telling the model what went wrong."""
    out = ""
    for _ in range(retries + 1):
        out = llm.complete(system, user, json_mode=True, **kw)
        try:
            return parse_json(out)
        except json.JSONDecodeError:
            user += "\n\nYour previous reply was not valid JSON. Reply with ONLY valid JSON."
    raise ValueError("Model did not return valid JSON. Start of its reply: " + out[:300])


def _norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[\s*_`|]+", " ", s).strip()  # ignore markdown bold / table pipes when matching quotes


def wrap_doc(d) -> str:
    age = d.age_days(TODAY_DATE)
    attrs = (f'id="{d.id}" file="{d.filename}" published="{d.date}" age_days="{age if age is not None else "unknown"}" '
             f'declared_type="{d.doc_type}" injection_suspected="{"true" if d.injection else "false"}"')
    return f"<document {attrs}>\n{d.text}\n</document>"


# ---- Step 1: per-document claim extraction + deterministic quote check -----------------
def extract(system, step_prompt, doc, log):
    data = llm_json(system, f"{step_prompt}\n\n{wrap_doc(doc)}", max_tokens=3500)
    body = _norm(doc.text)
    kept, dropped = [], 0
    for c in data.get("claims", []):
        quote = _norm(str(c.get("quote", "")))
        if quote and quote in body:
            c["doc"] = doc.id
            kept.append(c)
        else:  # the model's "evidence" is not actually in the document -> do not trust the claim
            dropped += 1
            log.append(f"{doc.id}: dropped claim with unverifiable quote: {c.get('text', '')[:80]}")
    data["claims"] = kept
    data["doc"] = doc.id
    data["dropped_claims"] = dropped
    age = doc.age_days(TODAY_DATE)
    data["age_days"] = age  # computed by code, not by the model
    if doc.injection:
        data.setdefault("red_flags", []).append("CODE-DETECTED text aimed at an AI/summariser: " + "; ".join(doc.injection))
        log.append(f"{doc.id}: injection-like text detected -> document excluded as evidence")
    return data


# ---- Step 2: cross-document reconciliation ---------------------------------------------
def reconcile(system, step_prompt, extractions):
    return llm_json(system, f"{step_prompt}\n\n<extractions>\n{json.dumps(extractions, ensure_ascii=False, indent=1)}\n</extractions>", max_tokens=3500)


# ---- Step 3: write the brief ------------------------------------------------------------
def write(system, step_prompt, usable, recon, excluded_notes, feedback=None):
    user = (f"{step_prompt}\n\n<extractions>\n{json.dumps(usable, ensure_ascii=False)}\n</extractions>\n\n"
            f"<reconciliation>\n{json.dumps(recon, ensure_ascii=False)}\n</reconciliation>\n\n"
            f"<excluded_documents>\n{json.dumps(excluded_notes, ensure_ascii=False)}\n</excluded_documents>")
    if feedback:
        user += f"\n\nA reviewer found these problems in your previous draft. Fix them:\n{json.dumps(feedback, ensure_ascii=False)}"
    return llm.complete(system, user, max_tokens=2000)


# ---- Step 4: critic ---------------------------------------------------------------------
def critique(system, step_prompt, brief, usable, excluded_notes):
    return llm_json(system, f"{step_prompt}\n\n<brief>\n{brief}\n</brief>\n\n<extractions>\n{json.dumps(usable, ensure_ascii=False)}\n</extractions>\n\n"
                            f"<excluded_documents>\n{json.dumps(excluded_notes, ensure_ascii=False)}\n</excluded_documents>", max_tokens=2000)


def check_citations(brief: str, doc_ids: set) -> list:
    problems = []
    for c in set(re.findall(r"\[(S\d+)\]", brief)) - doc_ids:
        problems.append(f"Cites unknown source {c}")
    for para in re.split(r"\n+", brief):
        if re.search(r"\d", para) and not re.search(r"\[S\d+\]", para) and not para.startswith("#") and len(para) > 40:
            problems.append(f"Line with numbers but no citation: {para[:70]}")
    return problems


def sources_section(brief: str, docs) -> str:
    cited = sorted(set(re.findall(r"\[(S\d+)\]", brief)), key=lambda s: int(s[1:]))
    by_id = {d.id: d for d in docs}
    lines = ["## Sources"]
    for c in cited:
        if c in by_id:
            d = by_id[c]
            lines.append(f"- **[{d.id}]** {d.source or d.filename} — {d.date or 'date n/a'} — {d.url or d.filename}")
    return "\n".join(lines)


# ---- Orchestration ----------------------------------------------------------------------
def run_pipeline(docs, ticker, prompts_dir, trace):
    system = load_prompt(prompts_dir, "system.md")
    ex_prompt = load_prompt(prompts_dir, "extract.md")
    extractions = [extract(system, ex_prompt, d, trace["log"]) for d in docs]
    trace["extractions"] = extractions

    recon = reconcile(system, load_prompt(prompts_dir, "reconcile.md"), extractions)
    trace["reconciliation"] = recon

    # Hard exclusion done in CODE (not left to the writer's judgement):
    excluded_notes = {x["doc"]: "different entity: " + str(x.get("why", "")) for x in recon.get("wrong_entity", []) if "doc" in x}
    for d in docs:
        if d.injection:
            excluded_notes[d.id] = "contains instructions aimed at an AI: " + "; ".join(d.injection)
    usable = [e for e in extractions if e["doc"] not in excluded_notes]
    trace["excluded_documents"] = excluded_notes

    write_prompt = load_prompt(prompts_dir, "write.md").replace("{{TICKER}}", ticker)
    brief = write(system, write_prompt, usable, recon, excluded_notes)
    trace["draft_1"] = brief

    issues = check_citations(brief, {d.id for d in docs})
    issues += critique(system, load_prompt(prompts_dir, "critic.md"), brief, usable, excluded_notes).get("issues", [])
    trace["critic_issues"] = issues
    if issues:
        brief = write(system, write_prompt, usable, recon, excluded_notes, feedback=issues)
        trace["draft_2"] = brief
        trace["log"].append(f"Rewrote once after {len(issues)} critic issue(s).")
    return brief


def run_single_shot(docs, ticker, prompts_dir, trace):
    """Baseline: one prompt, all documents, no checks. Used to compare against the pipeline."""
    system = load_prompt(prompts_dir, "system.md")
    user = load_prompt(prompts_dir, "write.md").replace("{{TICKER}}", ticker) + "\n\n" + "\n\n".join(wrap_doc(d) for d in docs)
    return llm.complete(system, user, max_tokens=2000)
