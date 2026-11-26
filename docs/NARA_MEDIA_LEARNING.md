# Local audio and video learning

Nara archives the original bytes and SHA-256 before attempting extraction.
For local audio or video files up to 500 MB and 15 minutes:

```sh
nara mission learn-media-ingest /absolute/path/lesson.mp4 --modality video --extract-local --language pt
nara mission learn-media-show SOURCE_ID
nara mission learn-media-propose SOURCE_ID "The lesson recommends X" --quote "exact words in transcript"
nara mission learn-media-frames SOURCE_ID
nara mission learn-repo-verify SOURCE_ID --quote "github.com/OWNER/REPOSITORY"
```

The `nara_learning_ingest` agent tool accepts the same `path`, `modality`,
`extract_local: true`, and optional `language` fields (Portuguese by default).
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

Extraction uses local `ffprobe` and `ffmpeg` to decode mono 16 kHz WAV, then
Nara's installed local STT backend. It never falls through to a cloud STT
provider. The transcript is stored by content hash, linked to the original
source hash and duration. The original remains available even if decode or STT
fails; the source keeps `needs_extraction` and records the error for a retry.
Re-running extraction on an intact local transcript returns the same source.

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
`ffprobe` must be on `PATH`. Larger media, full scene/clip understanding,
word timestamps, remote URL acquisition, and automated claim verification
require separate adapters and evaluations. The current command does not claim
those abilities.
