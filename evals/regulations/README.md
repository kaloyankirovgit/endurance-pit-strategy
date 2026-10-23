# Eval: retrieval over the WEC sporting regulations

Does keyword search put the regulation clause that answers a question near the top? This measures retrieval only. No answer is generated yet.

## The questions

`questions.json` holds 36 questions, written for this eval:

- **30 answerable**, about the 2026 rules. Each is worded the way a race engineer might ask it, not copied from the regulation, and lists the article or articles that answer it. The articles were checked against the regulation text.
- **6 unanswerable**, about things the sporting regulations don't contain: Balance of Performance figures, race results, tyre compounds, stewards' decisions, lap records.

The runner also asks the answerable questions of the 2024 and 2025 regulations, wherever an article with the same heading exists. Those answers are mapped by heading and not checked by hand.

## How it runs

```
pip install -e ".[rag]"
python -c "from endurance_strategy.io.regulations import download_regulations; download_regulations()"
python -c "from endurance_strategy.rag.regulations import build_chunks; from endurance_strategy.paths import RAW_DIR, INTERIM_DIR; build_chunks(RAW_DIR / 'regulations' / '_manifest.json', INTERIM_DIR / 'regulation_chunks.jsonl')"
python scripts/run_retrieval_eval.py
```

- The PDFs and the chunks stay local, like the timing data. Only the questions, the code and the scores (chunk IDs, not regulation text) are committed. Raw answer logs quote the regulations, so they stay local too, and only their summaries are committed.
- Scoring is recall@k: does an answering chunk appear in the top *k*? It's reported as a count with the number of questions.

## Results

First run, 2026-10-23 (full write-up in E-009 of `docs/EXPERIMENT_LOG.md`):

| Setting | Questions | recall@1 | recall@3 | recall@5 |
|---|---:|---:|---:|---:|
| 2026, season filter | 30 | 15 | 20 | 24 |
| 2024 and 2025 versions, season filter | 52 | 30 | 39 | 46 |
| All seasons, no season filter | 82 | 15 | 44 | 49 |

- Most misses come from different words for the same thing ("top up" and "replenishment").
- Without the season filter, the right article from the wrong year comes out on top for 30 of 82 questions.
- Unanswerable questions score as high as answerable ones, so refusal can't rely on a score cut-off.

## Answers (E-010)

`python scripts/run_answer_eval.py` runs every question through the router, the answerer and the checker in `src/endurance_strategy/rag/answer.py`, 3 times each. It also runs the 6 routing cases in `routing.json`. Key facts in `questions.json` (short strings such as "60") are checked in the final answer.

- **Routing:** 18 of 18 runs sent the right way.
- **When retrieval found the right clause:** the answer cited it in 72 of 72 runs.
- **When retrieval missed:** 12 refusals and 6 honest partial answers, out of 18 runs.
- **Unanswerable questions:** all 18 runs were sent to "out of scope" by the router, so the answerer's own refusal still needs in-scope test questions.

## Car class (E-012)

`python scripts/run_answer_eval.py --questions questions_class.json --no-routing` runs 5 questions once per class plus 3 LMP2 questions. The class is passed in as a choice, not read from the question.

- **Chosen class's fact present:** 30 of 30 runs. The other class's fact showed up in 1 of 24 checked runs (a correct answer that also named the Hypercar rule).
- **LMP2:** refused in code in 9 of 9 runs, because the WEC regulations cover only Hypercar and LMGT3.
- Retrieval ignores the class. A clause that names one class often applies to all, and adding the class to the query cost recall.

## Embeddings against BM25 (E-011)

`python scripts/run_retrieval_comparison.py` compares BM25, a local embedding model and a hybrid on `questions.json` and on `questions_heldout.json`. The held-out questions were written before any embedding ran.

| Set | BM25 recall@5 | Embeddings recall@5 | Hybrid recall@5 |
|---|---:|---:|---:|
| Original (30) | 24 | 27 | 27 |
| Held-out (30) | 27 | 27 | 29 |

On the held-out set the differences come down to a few questions, which 30 can't settle, so BM25 stays the default (D-020).

## What it can't show

- 30 hand-written questions from one author is a small set. One question moves recall by about 3 points.
- The same model family helped write the questions and build the retriever.
- Nothing has been tuned on these questions. Any improvement has to be reported on a fresh set.
