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
