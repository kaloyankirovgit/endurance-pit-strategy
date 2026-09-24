# Rule: RAG and the LLM layer

The retrieval and explanation layer sits **around** the numerical system, never inside it.

---

## The responsibility boundary

**The LLM may:**

- interpret user intent
- select relevant regulation documents
- choose simulator inputs from an approved, validated schema
- call the simulator or optimiser as a tool
- summarise the numerical results it receives
- explain assumptions and uncertainty
- cite the documents it used

**The LLM may not:**

- change simulator equations or parameters outside the approved schema
- invent numerical values
- determine pit timing in prose
- override regulatory constraints without document evidence
- present an uncited regulation as fact
- restate a tool's numerical output with different numbers

**Every number in a generated answer must be traceable to a tool call or a retrieved document.** If a number appears that came from neither, that is a defect, and it should be detectable: log tool inputs and outputs alongside the generated text so the trace can be checked.

This boundary is what separates this project from a chatbot with a racing theme. It is also the part an interviewer is most likely to probe, because it is where most LLM projects are weakest.

---

## Source provenance

The corpus is **authoritative documents only**:

- FIA WEC Sporting Regulations
- technical regulations where they constrain strategy
- official event bulletins and sporting notices
- race-control documents

Not: forum posts, news articles, results aggregators, or anything a search engine returns. This is not a general web-search chatbot.

Regulation PDFs are stored locally and not committed. The registry in `docs/research/regulations.md` records what was retrieved, from where and when.

---

## Document versions

Regulations are season- and event-dependent, and bulletins amend them mid-season. A retrieved clause without a version is not usable.

Every chunk carries:

```
document_id      document_title    season
document_revision                  effective_date
section          page              source_url        text
```

The retriever must be able to answer "which version of this rule applied at this event?", not merely "what does the rule say?". A clause that was superseded before the target event is a wrong answer regardless of how well it matches the query.

---

## Chunking

- Chunk on document structure (sections and articles), not on a fixed character count. Regulations are written in numbered clauses, and a clause split across two chunks retrieves as neither.
- Never split a clause from its identifying number, or a table from its header.
- Preserve section and page metadata through chunking. The page number is what makes the citation checkable.
- Keep enough surrounding context that a retrieved chunk is interpretable alone: a clause reading "this does not apply in the case of (c)" is useless without (c).

---

## Retrieval evaluation, separately from generation

Retrieval quality is measured independently of answer quality. A fluent answer over wrong documents is worse than no answer, and only separate evaluation detects it.

- Build a held-out question set with known correct source passages. This must be constructed by hand: it is the expensive part and it is not skippable.
- Measure retrieval directly: does the correct passage appear in the top *k*?
- Report the metric with the question-set size. A recall figure over 12 questions is a different claim from one over 200, and the honest version states which.
- Evaluate the failure cases specifically: near-miss clauses, superseded versions, and questions the corpus genuinely cannot answer.

**A RAG claim on a CV is only defensible if retrieval was evaluated.** Calling an embedding API is not a RAG system.

---

## Citations

- Every regulatory claim in an answer traces to a specific retrieved chunk, with document, revision, section and page.
- No generic citation such as "per the sporting regulations" without an identifiable source.
- Citations point to what was actually retrieved and used, not to what would be plausible. A citation that does not support the sentence it is attached to is a fabrication even when the document is real.

---

## Refusal and uncertainty

The system must **refuse rather than guess** when the retrieved documents do not support the claim.

Required behaviours:

- No relevant document retrieved → say so; do not answer from parametric knowledge.
- Documents are ambiguous or conflicting → report the conflict, cite both.
- The question concerns an event-specific bulletin that has not been collected → say the corpus does not contain it.
- The question asks for a number the simulator has not produced → call the tool or decline. Do not estimate.

Refusal behaviour is tested like any other behaviour, with cases whose answers are deliberately absent from the corpus.

---

## Separation of retrieval from generation

Two stages, independently inspectable:

```
query → retrieval → retrieved chunks (inspectable, evaluable)
                          ↓
                    generation → answer with citations
```

Log the retrieved set for every answer. If an answer is wrong, it must be possible to tell whether retrieval failed or generation failed. Without the log they are indistinguishable, and the system cannot be improved.

---

## LLM-assisted ETL

An LLM may help structure PDF and race-control text (flag messages, event timestamps, regulation clauses), but it is never a source of truth. The pattern:

```
PDF / text → deterministic extraction → candidate structured records
→ LLM-assisted normalisation → schema validation
→ human spot-checking → stored record with provenance
```

Every LLM-produced record retains provenance recording that an LLM produced it, and schema validation happens *after* the LLM step, never before it. A record that fails validation is rejected, not repaired by another LLM call.

---

## Build order

Simplest thing that works, first:

1. Structural chunking with metadata, keyword or embedding retrieval, citations. Possibly no vector store: the corpus is small.
2. Retrieval evaluation on a hand-built question set.
3. Tool calling against a fixed simulator schema.
4. A vector store only if simple retrieval is measurably insufficient.
5. An agent framework only if the workflow genuinely needs multi-step planning.

Direct tool calls against a defined schema are more auditable, easier to test, and far easier to explain in an interview than a framework's abstractions.
