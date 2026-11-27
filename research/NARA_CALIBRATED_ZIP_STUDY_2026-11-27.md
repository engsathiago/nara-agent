# Calibrated ZIP study oracle — 2026-11-27

This increment provides one concrete executable domain verifier for the existing
protocol-v4 automatic curriculum queue. It does not establish a universal verifier
or learned competence from successful calibration alone.

## Frozen implementation and first real acquisition

Initial frozen code: `ce24259c2e636d23a8b4b83bab1bafcb6033bfae`.
Local model selected: `qwen3.5:4b`, installed digest
`7f3251fa6878a78a606bcb3c074283306e5ad2ea411a7774a9dd98a4bc7f2d13`.
The opt-in harness freezes an exported protocol and queues it through the actual
Nara mission CLI in a disposable profile. It supplies no hand-authored exercise
cases. The real worker owns web acquisition, curriculum generation, domain
validation, practice, reserved transfer and optional native admission.

The first real acquisition found
<https://docs.python.org/3/library/zipfile.html>. Its web extractor returned 48,549
characters after a requested limit of 48,000: bounded page text plus a paging
footer. The consumer rejected the response before any curriculum/model call.
No exercise or reserved result was generated, and no skill was activated.

- Profile: `/private/var/folders/c4/sn_zf7557_1gcpsyy2qtvwzr0000gn/T/nara-live-zip-study-pujfeoqg`
- Mission: `study-job-b8b6ead694030e9ef2d627ee`
- Protocol SHA-256: `5f15810677b8f6a8310e895f8dbc6b70cad7c0341a2d222dda5990bfd8a9ebce`
- Extraction receipt SHA-256: `6b38ce46840ead74b6e79a8cbb0a4b1cffeaee110af06c8846cfb1a8937ada6d`
- Work stdout SHA-256: `a209e04c308f80a5cb8b8912e9d90bea840e247cddd4d599f97e7c3809a5be8b`

A new regression reproduced the failure: five existing tests passed and the long
extraction case failed. The consumer now keeps the complete tool response in its
original hashed receipt, while passing at most 48,000 characters to study. Source
metadata records the retained character window, received length, received text
hash and truncation status. This is a window of the extractor's response, which
may itself have been truncated; it is not a claim to archive the entire web page.
The 1 MB tool-response bound is unchanged.

## Verifier contract

The domain contract follows the public
[Python zipfile reference](https://docs.python.org/3.14/library/zipfile.html).
The oracle builds real ZIP files, computes member metadata using Python, and
requires an exact JSON artifact produced by the actual Nara terminal. It checks
nested paths, directory entries and uncompressed byte counts. Calibration includes
positive and deliberately incorrect results; a failed calibration prevents export.
The native canary uses the normal skill preloader with the exact staged file hash.

Generated questions are limited to three known API facts and must cite matching
source spans; the explanation must equal an actual relevant span. Each split must
have a different archive topology. This does not prove semantic independence for
other domains, or general factual correctness merely because a source is cited.
Successful task execution without positive improvement is not admission evidence.

## Real source-grounded abstention

After the excerpt correction, frozen code `780c30ea4a` successfully acquired a
source. Search selected the Python general index instead of explanatory module
documentation. The real `nara_curriculum` call declined to invent a lesson from
that index. There were no generated cases, task evaluations or activated skills.
The result proves the source-grounded abstention path, not positive learning.

- Profile: `/private/var/folders/c4/sn_zf7557_1gcpsyy2qtvwzr0000gn/T/nara-live-zip-study-yagkqe_v`
- Mission: `study-job-a9f472e622c0572895886013`
- Source: <https://docs.python.org/3/genindex-all.html>
- Source SHA-256: `4cd4f689cea3d977407421e0b251e8da1d7bbe4cda8ccc3714f1e370453b188a`
- Generation receipt SHA-256: `e2ae68a36db521e2ba35dc3a145a8014813c2b7775f9880460ccc6e6264d41d1`
- Tokens: 16,267 input, 190 output; monetary cost unknown.
- Work stdout SHA-256: `c5e573d09413df851c290d07281f6332d76dbb4506e522326875d028b3dba61a`

The exported research protocol now uses a less symbol-heavy documentation query
and acquires up to three sources, allowing the existing relevance-comparison
consumer to choose among them. This addresses retrieval quality before any
exercise generation; it does not alter grading thresholds or tune against
reserved answers. Both prior outcomes remain part of the evidence.

## Independent terminal probe and integration corrections

A separate, hand-authored smoke task exercised the real CLI/gateway/terminal at
`780c30ea4aa352459890c16ce6564b788724557f`, without using curriculum or reserved
cases. Profile:
`/private/var/folders/c4/sn_zf7557_1gcpsyy2qtvwzr0000gn/T/nara-live-zip-terminal-dhxstrch`.
The model made four API calls (17,523 input and 590 output tokens). A Python tool
call failed with an undefined variable; subsequent commands produced a malformed
manifest. The CLI correctly returned exit 2 with
`max_iterations_reached(4/4)` and `completed: false`, despite a reassuring final
sentence. The oracle did not assign a task score or count this as improvement.

That probe also exposed two integration issues. A usage receipt can contain a
numeric accumulated cost while `cost_status` is `unknown`; the oracle now omits
monetary cost unless the status is priced/included and auxiliary calls introduce
no further uncertainty. The one-shot CLI auto-starts a gateway, whose normal idle
lifetime outlasts a temporary case. The oracle now explicitly owns a gateway child,
waits for its PID-bound readiness, and terminates/reaps that child on every exit.
It does not identify or stop other processes by command-line substring. Three
regressions failed before these corrections: two unknown-cost cases and cleanup
when the case raises. Readiness and cleanup are bounded within the evaluator's
120-second ceiling; failures never become positive task results.

## Final frozen run and limits

Frozen code `d15186004c965e5c1c6270a7f35fdbf98f426746` was exercised in two
independent ways. The repeated terminal smoke test in
`/private/var/folders/c4/sn_zf7557_1gcpsyy2qtvwzr0000gn/T/nara-live-zip-terminal-iod96yx0`
confirmed PID-bound gateway readiness and cleanup. Its owned child (PID 91966)
was reaped, with a lifecycle receipt. The model again exceeded four turns;
18,146 input and 762 output tokens were reported, with unknown cost. No task
score was assigned. This validates the execution/cleanup path, not task success.

The complete queue experiment then acquired three sources: current zipfile
module documentation, the Python 2.5 ZipInfo reference and the archiving overview.
The real source-comparison call hit its 120-second API timeout before returning
a selection. No curriculum or reserved exercises were generated and no skill was
activated. The queue settled as failed and preserved its original deadline,
request and failure receipt. The model's monetary cost remains unknown.

- Profile: `/private/var/folders/c4/sn_zf7557_1gcpsyy2qtvwzr0000gn/T/nara-live-zip-study-t_6onlxq`
- Mission: `study-job-bbe7b1d6b2a29122ed7b011c`
- Protocol SHA-256: `4cf1c85725d942c4ac2b8e310bf0fc6d45c16b07d7cc82c126fb9192419a0a8d`
- Comparison failure receipt: `b3bb1c14e74ebb614e84e7ae995eb52843a06a109d4c7c8680d8b25cc115859d`
- Work stdout SHA-256: `d14bdb4b04e58595222d0fc2ba08b0b1a6b9573e510fdaa14d7178c35f466bf9`

Offline reinspection checked 10, 15 and 17 content-addressed files for the three
queue experiments respectively, including each frozen protocol and work result.
The latter two runs' one and three stored source byte hashes were also verified.
These checks made no additional model or web calls. All profiles contained zero
admitted native skills. Full web-tool receipts stay local; only compact hashes
and outcomes are published here.

Final integrated tests passed **41 tests in five files**: oracle (10), research
(6), queue (11), curriculum (9), plugin registration (5). All **16 mandatory
checks** passed on the final code. The oracle tests include an actual exported
validator subprocess, calibration rejection, factual-answer rejection, renamed
exercise rejection, unknown costs, and an owned-process cleanup failure path.
They do not substitute for successful real-model curriculum, practice, reserved
transfer or native canary outcomes.

The next implementation need exposed here is bounded relevant source context:
sending entire acquired excerpts to the small local model is too expensive for
this comparison deadline. That change must preserve original spans, provenance
and replay of existing frozen protocols; increasing a timeout or loosening the
oracle until a trial passes would not establish improvement. Real generated
curriculum admission and positive transfer remain open. This increment does not
rebuild the Desktop binary, validate other hardware, or require a VPS.
