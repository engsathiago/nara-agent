# Reserved PT-BR retrieval gate

The 20 positive queries and four unrelated queries in `retrieval_holdout.json`
are reserved for one evaluation of a candidate embedding model and retrieval
algorithm. The development corpus is `retrieval_cases.json`. Do not tune the
algorithm against this holdout and then report the same run as independent.

Promotion threshold, declared before the run:

- hybrid top-1 at least 16/20;
- hybrid exceeds the lexical top-1 count by at least 8;
- zero retrieved memories on the four unrelated queries;
- every positive query reports `hybrid` mode, with no degraded fallback.

This small synthetic gate checks the local implementation and PT-BR paraphrase
behavior. It does not establish broad real-task performance or the best model
for every user domain. A later real-query dataset remains required for that
claim.
