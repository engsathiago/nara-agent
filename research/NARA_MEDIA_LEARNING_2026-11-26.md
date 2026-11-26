# Local media learning validation — 2026-11-26

The media path was exercised against the Nara bundled Python runtime built from
clean public `main` commit `04c395d044f3bce3f79ca5d89a4c101ac57164bb`.
That runtime includes `faster-whisper==1.2.1`. The **new source code** in the
media-learning branch was supplied through `PYTHONPATH`; the checkpoint DMG/ZIP
from `04c395d0` do not yet contain it.

The local macOS `say` voice Luciana generated the Portuguese sentence “A Nara
verifica resultados e preserva a fonte original.” FFmpeg converted it to a
16 kHz WAV, then muxed the same speech with a blue video into MP4. In separate
temporary Nara profiles, `nara_learning_ingest` with `extract_local=true` and
`language=pt` decoded each file through real FFmpeg and real local Whisper:

| Input | Source SHA-256 | Result |
| --- | --- | --- |
| WAV | `a4779c1977afa1b307c4aa346b8ea7d1a4e2822dd777e4140d299d318bf1d694` | `transcribed_local`, “a Nara verifica resultados e preserva a fonte original.” |
| MP4 | `38954f7b3a669243296a9295225fa9f695c1329355d1c31a0da2576b08352d5e` | `transcribed_local`, same Portuguese transcript |

Both calls reported provider `local` and preserved the original bytes. An
earlier run without an explicit Portuguese language produced an English
translation; the adapter now defaults to `pt`, and the repeated real run
returned the Portuguese wording. This validates the local ASR path on this
Mac and short synthetic speech, not accuracy on noisy Instagram posts or long
videos. Frame/OCR fusion, timestamps, remote acquisition and independent claim
verification remain outside this increment.

The focused tests exercise real FFmpeg decoding of generated WAV and MP4,
archived hashes, source-quoted candidate claims, visible STT failure, and
ingestion limits. They inject only the STT result for deterministic storage
assertions; the manual run above used the real backend.
