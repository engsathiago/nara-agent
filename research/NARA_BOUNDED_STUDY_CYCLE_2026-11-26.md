# Bounded source study with real development feedback

## Result

The production study cycle ran three source-grounded generations and three
development executions using local `qwen3.5:4b`. All three practice scores were
`0.5`: the refresh convention was correct, while the labels criterion remained
incorrect. The configured floor was `1.0`. The cycle stopped as `exhausted`,
left the gap `unresolved`, made **zero holdout executions**, recorded no new
demonstrated competence and activated no skill.

This proves execution of generation → practice → feedback → revision → bounded
stop on this real archived source. It does not prove successful learning transfer
or general autonomous improvement. There was no human editing of the candidate
procedures between attempts. No retry was made after observing this result.

## Frozen protocol

- Production code, evaluator and protocol were committed as `5ae73cadc7` before
  any generation in this experiment.
- Source: the previously archived public Instagram post
  <https://www.instagram.com/p/DdFLWjqAfMC/>; SHA-256
  `46bafd75c32053dcac9115f5eca0164bfcd4ac281efd86cf2cd870ba7882f171`.
- Model digest:
  `7f3251fa6878a78a606bcb3c074283306e5ad2ea411a7774a9dd98a4bc7f2d13`.
- `evals/media_transfer/study_cycle_protocol.json`: one new development case
  and three reserved cases with new robot IDs/balances; SHA-256
  `29e9c9c3db4190d0517225717a1e3e2dbafe1edd87bfa16c870d2a74f50ca5a5`.
- Objective and scoring convention match the earlier office-display experiment.
  `office_labels_practice.py` is a separately frozen evaluator snapshot that
  additionally returns development feedback. The earlier evaluator is unchanged.
- Three generation calls maximum, 600-second admission deadline, 120-second
  evaluator timeout; study reasoning disabled and host transient retries set to
  zero in the isolated profile. No external provider or market account was used.

The evaluator checks live local-model responses, not candidate keywords. Only
the development case's input, observed score, expected output and feedback were
sent to later generations. Reserved inputs/results never entered those requests.
The cycle did not reach reserved baseline/candidate execution because no
development candidate met the floor.

## Evidence

Local profile basename: `nara-live-study-cycle-zic5nd_9`.
Plan ID: `e1971dc4ec57406d9142be0189d76131`.

| Attempt | Candidate ID | Practice score | Generation tokens |
| --- | --- | ---: | ---: |
| 1 | `e4738a0d8037861b9612` | 0.5 | 1,093 |
| 2 | `1bc5e6dbc6b93f9d71c0` | 0.5 | 1,536 |
| 3 | `955ade3ec5dc52162385` | 0.5 | 1,398 |

The first candidate repeats the deterministic initial proposal from the earlier
source-ID trial; later candidates were model-authored revisions based solely on
development feedback. Generation usage totals 4,027 tokens and excludes evaluator
inference. The host did not report generation price; cost remains explicitly
unknown, not a claimed zero-dollar measurement.

- Frozen cycle request:
  `97ce41e7b5d9ba307e5269468c238a52033e63cc0d113f9a6e53c7d4b46b28df`.
- Final cycle receipt:
  `1556fe055c590a8bac6e3fbdc0078ba055a3ecd512d4e325e7f2ac832fe03904`.
- Generation receipts, in order:
  `613954e5008750a4c1832f62fecca3000c1646d3d69c64879910e510eee79059`,
  `ddf909cb1d35c9f402fc2023a43cabdbd216642c8bc272a68dab08771e7c3f56`,
  `9ef78e372870c8a2d826efe57447b0a8f66e88d7ef03023e8cf180444618723a`.

`verify_study_cycle.py PROFILE` reopens the archived source, source spans,
generation requests/responses, exact unedited candidate steps, development-only
feedback chain, hashed observations and final receipt. It recomputes scores from
the observed model responses, without new inference. The local verification
passed. Full source text, quotations and raw model responses remain in the local
profile rather than being republished here.

## Remaining work

Automatic source discovery and gap dispatch, recovery of interrupted cycles,
stronger evidence of useful transfer, and longitudinal testing remain open.
This experiment does not update the Desktop binary or validate VPS deployment.
