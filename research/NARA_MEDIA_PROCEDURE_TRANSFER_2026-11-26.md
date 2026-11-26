# Media procedure transfer bridge — 2026-11-26

The Learning Fabric can now submit an **inactive** procedural candidate to
the existing Learning Lab. The proposal requires a repository claim verified
from the same source and one exact extracted-text quote per proposed step.
The candidate includes content hashes for the original media, a frozen
step-to-quote provenance record and the official GitHub response. It carries
the source URL, version and declared license (or `unknown`). The original,
transcript, frame evidence and API snapshot are checked again before both
evaluation and promotion. `learn-promote` still requires a frozen executable
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
