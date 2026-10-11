You will receive ONE document (its header attributes include publication date and age in days — use them, do not recompute).
Extract the claims in it that matter for a long-term investor.

Return ONLY JSON of this shape:
{
  "entity": {"name": "company name exactly as written", "business": "what it does, as written"},
  "source_type": "exchange filing | company press release | earnings call | news | broker/analyst | blog/forum/social | other",
  "age_label": "fresh (<3 months) | ageing (3-12 months) | stale (>12 months)",
  "red_flags": ["promotional tone, anonymous author, unsourced numbers, no SEBI registration, instructions aimed at an AI, hidden text, etc."],
  "claims": [
    {
      "text": "one claim in plain words, with exact numbers, units and period",
      "kind": "fact | management claim | opinion | forecast | rumour",
      "direction": "positive | negative | neutral",
      "quote": "an EXACT short verbatim quote (under 25 words) from the document that supports this claim"
    }
  ]
}
Rules: the quote must be copied character for character from the document, otherwise the claim is discarded.
Extract at most 12 claims, most decision-relevant first. Include negatives, risks, legal or regulatory items,
working-capital / debt / pledge / cash-flow quality items, and caveats — not only headlines.
Mark what the company itself says about its own legal or financial exposure as "management claim".
