# Local audio and video learning

Nara archives the original bytes and SHA-256 before attempting extraction.
For local audio or video files up to 500 MB and 15 minutes:

```sh
nara mission learn-media-ingest /absolute/path/lesson.mp4 --modality video --extract-local --language pt
nara mission learn-media-show SOURCE_ID
nara mission learn-media-propose SOURCE_ID "The lesson recommends X" --quote "exact words in transcript"
```

The `nara_learning_ingest` agent tool accepts the same `path`, `modality`,
`extract_local: true`, and optional `language` fields (Portuguese by default).
After reading the returned transcript, the
agent can call `nara_learning_claim_propose` with an exact source quote. A claim
stays a **candidate**; transcription or a plausible quote never counts as
independent verification or a promoted memory.

Extraction uses local `ffprobe` and `ffmpeg` to decode mono 16 kHz WAV, then
Nara's installed local STT backend. It never falls through to a cloud STT
provider. The transcript is stored by content hash, linked to the original
source hash and duration. The original remains available even if decode or STT
fails; the source keeps `needs_extraction` and records the error for a retry.
Re-running extraction on an intact local transcript returns the same source.

An installed local STT backend is required. The bundled Desktop runtime has
the optional local Whisper dependencies; a source checkout can install the
`stt-whisper` extra or configure Nara's local STT command. `ffmpeg` and
`ffprobe` must be on `PATH`. Larger media, frame/OCR fusion, word timestamps,
remote URL acquisition, and automated claim verification require separate
adapters and evaluations. The current command does not claim those abilities.
