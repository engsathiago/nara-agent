# Media procedure transfer bridge — 2026-11-26

The Learning Fabric can now submit an **inactive** procedural candidate to
the existing Learning Lab. The proposal requires one exact extracted-text quote
per proposed step. A repository claim verified from the same source is optional;
when supplied, its official GitHub evidence is retained and checked again.
The candidate includes content hashes for the original media and a frozen
step-to-quote provenance record. It carries the source URL, version and declared
license (or `unknown`). The original, transcript and frame evidence, plus any
attached API snapshot, are checked again before both evaluation and promotion.
`learn-promote` still requires a frozen executable
evaluator, reserved cases, baseline and candidate artifacts, and positive
transfer without regression; rollback remains available.

## Vertical evidence

- A three-second synthetic video displayed
  `github.com/ggml-org/whisper.cpp` only on screen. Local macOS Vision OCR
  extracted that exact URL from one archived frame.
- The production verifier queried the real GitHub API and returned a verified
  repository identity at a pinned commit.
- `LearningLab.propose_from_media` created inactive candidate
  `a4aac8742f2627fe532a`, with no active skill directory.
- The temporary-profile CLI test went from a quoted source and verified
  repository through candidate creation, a frozen subprocess evaluator on a
  reserved holdout, evidence-backed promotion and active memory. Separate
  assertions reject invented quotes, tampered originals and promotion before
  an eval exists.

The synthetic video's evaluator is a narrow integration fixture. It does not
show that a real Reel taught a useful procedure or that transfer improves on
varied tasks. That stronger claim still needs real media, a predeclared task,
reserved cases, independent scoring and regression checks. A candidate from
an external video remains an untrusted hypothesis until that proof passes.

## Media without a repository URL

The CLI and agent tool now accept the same inactive, exact-quote candidate
without `--repo-claim` / `repository_claim_id`. The local behavior test first
failed on the required CLI argument, then passed through proposal, denied
promotion without evaluation, a frozen reserved-case evaluator and promotion.
A second tool-path test confirmed that altering the original archive blocks
evaluation even without a repository. The quote proves provenance, not the
meaning or usefulness of the proposed step; the reserved transfer check is
still mandatory.

Three user-supplied public Instagram posts were acquired and locally extracted
with the previously built `6ae29a3` bundle in separate temporary profiles:
`DdJoMPhxsF1` (`source_hash` `6cc3fefa317156ad59875f0ea70dbcc098e18382cdf57c7c975af52ffc16ab4f`),
`DdHAb4hxAWc` (`cc38ee514b2262619eb7418be53985ad009a66b801bd0f85d3461ffb3a51f36d`),
and `DdHQhxZRwbq` (`43d7870d65f749036e0f21081f82a99b8434ffc64d1873242ca8c61bd10187ee`).
No `github.com/owner/repo` URL appeared in their combined extracted text.
These posts therefore cannot satisfy the repository-verification fixture; no
procedure from them was promoted or counted as demonstrated learning.
