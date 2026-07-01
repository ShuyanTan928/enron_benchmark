"""Step 1 (redesigned): generate a secret topic, then ground it on a REAL enron_10
email found by HyDE-style retrieval (query expansion + BM25 + LLM fit-judge).

Pipeline per topic:
  1a  gen_topic   — LLM writes one ABSTRACT secret (general idea, no specifics)
  HyDE            — LLM writes hypothetical concrete emails instantiating the true_fact/false_belief binary
  retrieve        — BM25 over the real emails, multi-query RRF fusion -> top-k (deduped)
  fit-judge       — LLM picks a same-KIND anchor email, or NONE
  specialize      — LLM rewrites the secret to fit that email's real specifics, or SKIP
  resolve         — chosen real email -> enron_anchor (real From/To/date/subject/body)

Casting (actor/victim) stays in Step 2; Step 1 keeps real identities on the anchor.
"""
