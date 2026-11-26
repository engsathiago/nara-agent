# Model-authored media study — negative live result

The new `nara mission learn-media-study SOURCE_ID --objective TEXT` command
uses `ctx.llm.complete_structured` through the registered `nara_media_study`
auxiliary slot. It verifies the archived source before generation and again
before creating an inactive procedure via the existing LearningLab. It never
runs evaluation or activates a skill implicitly. The same slot appears in the
host's model assignment surfaces and can follow the main model or use its own
operator-selected model. No provider SDK or model-specific route was added to
the plugin or core.

## Live protocol and observed result

The prompt, source, new cases and unchanged office-convention evaluator were
committed before inference. The final live configuration was frozen at
`d914e4051c`; `evals/media_transfer/run_model_study.py` records the reproducible
entry point. It imports the previously extracted public Instagram video with
SHA-256 `46bafd75c32053dcac9115f5eca0164bfcd4ac281efd86cf2cd870ba7882f171`
into a new temporary profile and invokes the actual registered CLI in a child
process. It does not pass the old hand-authored candidate, scoring rubric or
reserved cases to the generating model.

The local Ollama model was `qwen3.5:4b`, with observed installed digest
`7f3251fa6878a78a606bcb3c074283306e5ad2ea411a7774a9dd98a4bc7f2d13`.
The first launch stopped before inference because the isolated child lacked
the managed dependency path. The next attempt reached inference but timed out:
the host used default reasoning and retried the transport request. No candidate
or score was produced. The follow-up configured the dedicated study slot with
`reasoning_effort: none` and `auxiliary.transient_retries: 0`; no source, prompt,
case or scoring change was made in response to evaluation results.

The follow-up completed generation in approximately 15 seconds, using 565 input
and 365 output tokens. Its JSON proposed **10 steps and 8 quotes**, and one
quote was not an exact source substring. The production validator rejected it;
the CLI exited 1 with a durable failure receipt:
`89564ad5143c32ecf3eed0d61fde5d20acd6cb04049e4cb4d5c91e136ce6de9f`.
Its request receipt is
`0ad6404ef62af728cdacff1524fa57f01453a3d7f131871740c9421e6a68c93c`.
An independent read recomputed both hashes and confirmed the cardinality,
one nonliteral quote, zero candidate files and zero active learned skills.
The request and full response remain in the temporary local profile; they are
not republished here because they contain the source transcript and excerpts.
No candidate, reserved evaluation, skill promotion or rollback was performed
for this live attempt. The owner's active profile was untouched.

This is evidence that the real model route, source ingestion and rejection
path work. It is **not** evidence that this model can reliably author useful
skills or that the autonomous learning gate has passed. There was no manual
repair or selection of another generated candidate. The earlier successful
hand-authored transfer experiment remains a separate result.

## Validation and remaining work

The initial implementation passed 69 focused tests across 12 learning/plugin
files. After the auxiliary slot was added, its updated registration and study
tests passed 14 cases. They exercise inactive-candidate creation, source
integrity before and after generation, invalid/mismatched citations, an explicit
no-procedure response, reserved evaluation, promotion and rollback using a
deterministic model fixture. Later diagnostics distinguish generation failures
from proposal validation errors and avoid archiving transport error secrets.
The final two updated files passed 15 tests, including transport-error
redaction; `scripts/check --staged` passed all 16 checks.

Automatic source discovery, independent evaluation construction, robust
model-authored proposals and varied-task transfer remain open. The current
Desktop archives have not yet been rebuilt with this command. VPS deployment
remains the separate later stage requested by the owner.
