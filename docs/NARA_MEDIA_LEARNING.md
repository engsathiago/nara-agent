# Local audio and video learning

Nara archives the original bytes and SHA-256 before attempting extraction.
For local audio or video files up to 500 MB and 15 minutes:

```sh
nara mission learn-media-ingest /absolute/path/lesson.mp4 --modality video --extract-local --language pt
nara mission learn-media-fetch-status
nara mission learn-media-fetch https://www.instagram.com/reel/POST_ID/ --extract-local --language pt
nara mission learn-media-show SOURCE_ID
nara mission learn-media-propose SOURCE_ID "The lesson recommends X" --quote "exact words in transcript"
nara mission learn-media-frames SOURCE_ID
nara mission learn-repo-verify SOURCE_ID --quote "github.com/OWNER/REPOSITORY"
nara mission learn-media-procedure SOURCE_ID --repo-claim VERIFIED_CLAIM_ID --name "Inspect repository" --step "Inspect the pinned commit" --quote "exact words from the video"
nara mission learn-evaluate CANDIDATE_ID --cases-file /absolute/path/cases.json --evaluator /absolute/path/evaluator.py --development-case DEVELOPMENT_CASE_ID
nara mission learn-promote CANDIDATE_ID
```

The `nara_learning_ingest` agent tool accepts the same `path`, `modality`,
`extract_local: true`, and optional `language` fields (Portuguese by default).
The `nara_learning_fetch` tool accepts a public video URL and the same extraction
options. Fetch uses the pinned `media-fetch` package extra or an installed
`yt-dlp` command, with configuration and browser cookies disabled. The bundled
Desktop package includes the pinned extra. It accepts one public Instagram post/Reel, YouTube video, or Vimeo
video over HTTPS, then sends the temporary download through the local file
ingestion path. The download directory is removed; the content-addressed source
archive remains for provenance and later re-extraction. `learn-media-fetch-status`
reports whether the optional extractor is available. Authentication-only posts,
expired Stories, rate limits, and site changes produce an explicit error.
After reading the returned transcript, the
agent can call `nara_learning_claim_propose` with an exact source quote. The
`nara_learning_frame_extract` tool retries video screen OCR separately. A claim
stays a **candidate**; transcription or a plausible quote never counts as
independent verification or a promoted memory.

If the transcript or screen OCR contains an exact GitHub repository URL, the
`learn-repo-verify` command or `nara_learning_repo_verify` tool checks that
repository against GitHub's public REST API, pins the current commit SHA, and
archives both official responses by hash. The resulting verified claim says
only that the repository identity exists at that commit. It does **not** verify
the video's claims about features, quality or safety and does not install or
activate a skill. A missing repo, mismatched identity, API limit or changed
archived response produces an explicit error. The caller can inspect the
`primary_sources` record on the source and the returned evidence hash. This
uses GitHub's documented [repository](https://docs.github.com/en/rest/repos/repos)
and [commit](https://docs.github.com/en/rest/commits/commits) endpoints.

After repository verification, `learn-media-procedure` (or
`nara_learning_media_procedure_propose`) can create an **inactive** procedural
candidate. Each proposed step needs an exact quote present in the extracted
speech or screen text. The candidate carries the original hash, source URL,
declared license or `unknown`, quote-to-step mapping, verified repository claim
and archived API evidence. A quote grounds the proposal; it does not prove the
step works. Promotion uses the same frozen evaluator, reserved holdout,
baseline/candidate evidence, and rollback as procedures learned from verified
missions. The source and archived evidence are rechecked before evaluation and
promotion. `nara mission learn-rollback CANDIDATE_ID` disables a promoted skill.
The operator must supply meaningful, independent cases and the executable
evaluator; a passing toy fixture does not establish general competence.

Extraction uses local `ffmpeg` to decode mono 16 kHz WAV, then
Nara's installed local STT backend. It never falls through to a cloud STT
provider. The transcript is stored by content hash, linked to the original
source hash and duration. The original remains available even if decode or STT
fails; the source keeps `needs_extraction` and records the error for a retry.
Re-running extraction on an intact local transcript returns the same source.
With faster-whisper, `learn-media-show` also exposes
`metadata.local_extraction.timing`: native speech segments with `start` and
`end` in seconds and their text, plus the JSON archive path and SHA-256.
The segments use the same confidence filter as the transcript. Their evidence
is checked on cached extraction and before source citation or procedure
evaluation. A changed archive produces an error; preserve it for diagnosis
and restore the original evidence from a trusted backup before retrying.
Text-only local command backends report `timing.status: unavailable`; Nara
does not infer timestamps from text length. Earlier sources without a timing
record remain readable. Segment boundaries are model estimates, not word
alignment or a guarantee of acoustic accuracy.
Duration is checked with `ffprobe` when present, or the installed PyAV backend
when `ffprobe` is absent. The Desktop bundle carries PyAV and the pinned
FFmpeg executable; a source install needs `ffmpeg` and either `ffprobe` or PyAV.

For videos, the same ingest also samples up to 60 frames, at least 0.5 seconds
apart, and runs local OCR. On macOS it uses the system Vision framework through
the Swift toolchain; elsewhere it can use an installed Tesseract with Portuguese
and English language packs. It archives at most 20 distinct text-bearing frames,
each with a frame hash and sampled time, and joins the on-screen text with the
speech transcript. A repository name appearing only on screen can therefore be
cited as a candidate claim. If speech or OCR fails, the other result remains
available and the failure appears in source metadata. The frame times describe
sample points, not word-level timestamps; brief text between samples can be
missed. Re-running `learn-media-frames` returns completed OCR evidence after
checking archived frame and fused-text hashes; changed evidence fails visibly.

An installed local STT backend is required for speech extraction; screen OCR
can still succeed on a silent video. The bundled Desktop runtime has
the optional local Whisper dependencies; a source checkout can install the
`stt-whisper` extra or configure Nara's local STT command. `ffmpeg` and
Source installs without the `media-fetch` extra also need a `yt-dlp` command
on `PATH`.
Larger media, full scene/clip understanding, word timestamps, and broad
automated claim verification require separate adapters and evaluations.
