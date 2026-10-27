"""Step 4 - the AI writes a short summary and an email DRAFT from verified facts only."""

SYSTEM_PROMPT = (
    "You are a careful B2B sales researcher. Write ONLY from the verified facts provided. "
    "Do not add any other claim, number, event or compliment about the company. "
    "If a fact is not in the list, it does not exist for you. "
    "The email is a draft for a human to review; never pretend to know the recipient's name or "
    "role (use the placeholder [Recipient name]). Return only a JSON object."
)


def build_draft_prompt(company, facts, scoring, icp, include_email=True):
    seller = icp["seller"]
    lines = []
    for field, f in facts.items():
        if f["status"] == "verified":
            lines.append(f'- {field}: {f["value"]} (evidence: "{f["evidence"]}")')
    verified_block = "\n".join(lines) or "- (no verified facts)"
    task = (
        'Return a JSON object with:\n'
        '- "summary": 2-3 plain sentences summarizing the company, using only verified facts. '
        "Use figures exactly as stated in the evidence; never mention internal category labels "
        "such as size bands.\n"
    )
    if include_email:
        task += (
            '- "subject": email subject line, under 9 words.\n'
            '- "body": email under 100 words. Start with "Hi [Recipient name],". Open with ONE '
            "specific verified fact about the company (prefer the growth_signal evidence if present). "
            "Then one sentence on how the seller's product helps, in your own words (do not copy the "
            "product description). Do not mention negative events, the score, or size bands. "
            f'End with a low-pressure question and sign off "{seller["sender"]}".'
        )
    return (
        f"Seller: {seller['company']}. Product: {seller['product']} "
        f"Value: {seller['value_proposition']}\n\n"
        f"Prospect company: {company}\n"
        f"Lead score: {scoring['score']}/100 ({scoring['tier']})\n"
        f"Verified facts:\n{verified_block}\n\n{task}"
    )


def validate_draft(draft, include_email=True):
    keys = ("summary", "subject", "body") if include_email else ("summary",)
    if not isinstance(draft, dict) or not all(
        isinstance(draft.get(k), str) and draft[k].strip() for k in keys
    ):
        raise ValueError(f"Draft must contain non-empty {', '.join(keys)}")
    return {k: draft[k].strip() for k in keys}
