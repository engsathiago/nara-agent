# Nara policy, authority, and privacy specification

Status: implemented foundation, version 1  
Default profile: `default-observe-only-v1`  
Authority: Mission Control Policy Decision Point (PDP)

## 1. Objective and boundary

The PDP is the single Nara-owned decision layer for actions proposed through CLI, voice, gateway,
subagents, and fleet workers. It does not replace model/provider limits or operating-system access
control. It does not silently add behavioral refusals: the shipped profile is `observe_only`, has no
rules, and therefore returns `allow` while recording a redacted receipt.

Rules are configuration, not core code. A policy version is immutable after staging. Promotion is
atomic, retains its parent, and can be rolled back. A model cannot treat its own statement as an
approval.

## 2. Decision contract

Input:

- action/tool name;
- target projected from structured arguments;
- authenticated actor identifier supplied by the runtime;
- surface (`cli`, `voice`, `gateway`, `subagent`, `fleet`, or `runtime`);
- active policy version.

Output:

- `allow`;
- `require_confirmation`, with a one-use approval bound to the exact decision fingerprint; or
- `deny`.

Each decision stores version, action, target kind, target SHA-256, actor, surface, matched rule,
reason, effective result, and the result that an observe-only profile would have produced. Raw
target content is not stored in the policy receipt.

Rules match action, target, and surface with deterministic glob patterns and explicit priority.
They must have unique IDs and one of the three effects. Control tools for status, explanation,
one-use confirmation, and rollback remain available so a broad rule cannot permanently lock the
owner out. Staging and promotion remain policy-governed.

## 3. Confirmation protocol

1. The first exact call produces `require_confirmation` and a decision ID.
2. The owner inspects it with `nara_policy_explain`.
3. `nara_policy_confirm` creates one approval for that exact fingerprint.
4. One retry consumes the approval.
5. A second retry requires a new approval.

Changing actor, target, action, surface, or policy version changes the fingerprint. Confirmation is
therefore not a reusable bypass token.

## 4. Authentication and authority

Nara reuses the authentication boundary of each transport: dashboard auth for web, platform account
identity for gateways, local OS/profile ownership for CLI, and registered host identity plus worker
lease for fleet. The PDP consumes the resolved actor; it never accepts a model-written claim that an
actor is authenticated. Deployment must fail closed when a transport cannot supply the identity
required by an active rule.

The default local profile intentionally has no extra Nara authorization restrictions. Operators can
stage rules for installation, publishing, commercial actions, external contact, bots, media,
filesystem scopes, or remote execution without changing agent code.

## 5. Secrets and trace content

Audit projections recursively redact values whose keys identify credentials, authorization,
cookies, passwords, private keys, secrets, session tokens, or API tokens. Common inline
`KEY=value` secret forms are also redacted. A short SHA-256 correlation digest remains so repeated
exposure can be diagnosed without retaining the value.

Policy receipts retain only the target digest. Effect receipts retain a sanitized target.
Transcripts are represented by hash and character count unless a future explicit privacy profile
enables storage. Secrets must live in the existing provider/OS secret mechanisms, not policy rules.

## 6. Privacy defaults

The local profile starts with:

- telemetry disabled (opt-in only);
- sensitive trace content disabled/redacted;
- voice transcript storage disabled;
- camera disabled;
- biometric processing disabled;
- media retention set to zero days until an operator chooses a period.

Settings are stored under the active `NARA_HOME`, which isolates profiles. Configuration changes are
explicit and validated. `nara_privacy_export` writes a non-overwriting, hashed export of the privacy
profile. Full state export, restore, and deletion are handled by the Phase 10 profile backup tool so
referential integrity across missions, memories, artifacts, skills, and evaluations is preserved.

## 7. Retention, export, and deletion

Backups are content-hashed manifests. Restore refuses path traversal, unexpected files, and hash
mismatches. A profile deletion is never inferred from a chat request with an ambiguous target; the
operator must select the exact archive/profile path. Destructive deletion is outside unattended
execution. Individual artifacts remain linked to mission retention metadata so pruning cannot leave
a mission falsely claiming that evidence exists.

## 8. Promotion and rollback gate

A candidate policy can be promoted only after:

- schema validation;
- surface-consistency tests on CLI, voice, gateway, subagent, and fleet contexts;
- confirmation binding and one-use consumption tests;
- lockout recovery and rollback tests;
- secret-redaction tests;
- a canary using a temporary profile, never the personal profile;
- operator review of rules and expected decisions.

Rollback restores the recorded parent version atomically. Policy promotion is independent of model
or skill promotion.

## 9. Current guarantees and open deployment gates

Implemented and tested locally:

- versioned rules, staging, atomic promotion, explanation, one-use confirmation, denial, and rollback;
- a transparent default profile with no added Nara refusal behavior;
- consistent deterministic decisions across the five named surfaces;
- redacted policy/effect receipts and local privacy defaults;
- dashboard projection from the canonical policy/privacy stores.

Deployment gates that require the target environment:

- verify the concrete authenticated actor mapping for each enabled gateway;
- verify VPS host identity and transport configuration;
- choose the owner-approved production rule set;
- choose retention periods and any explicit telemetry destination.

Until those choices are made, Nara remains on the local observe-only profile and no production
policy is represented as approved.
