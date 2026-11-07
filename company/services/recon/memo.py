"""Exception memos for unmatched transactions.

When a statement line can't be matched to a ledger entry, we ask an LLM to
draft a short memo for the customer's ops team explaining the likely cause
(duplicate, timing difference, fee, FX). Shipped in the 2026-08 release.
"""
import os

import anthropic

client = anthropic.Anthropic(api_key=os.environ["LLM_API_KEY"])  # prod/recon/llm-api-key

PROMPT = """You are a reconciliation analyst. Explain why this bank statement
line did not match any ledger entry, in two sentences.

Statement line: {line}
Nearest ledger candidates: {candidates}
"""


def draft_memo(statement_line: dict, candidates: list[dict]) -> str:
    # statement_line includes counterparty name, amount, value date and the
    # free-text remittance field exactly as it appears on the customer's statement.
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": PROMPT.format(line=statement_line, candidates=candidates)}],
    )
    return msg.content[0].text
