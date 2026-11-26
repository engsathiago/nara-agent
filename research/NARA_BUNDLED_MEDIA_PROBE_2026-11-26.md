# Bundled media probe — 2026-11-26

The clean macOS arm64 build from public main `b7eb3898b1d7ca6a7d2811aa4c127a8d0ec3f930`
completed successfully and staged pinned `yt-dlp 2026.08.19` in its own
Python environment. Its `nara mission learn-media-fetch-status` command
returned `available` on the normal host PATH and pointed to the executable
inside the app bundle.

With PATH restricted to `/usr/bin:/bin`, that same build initially returned
`unavailable`: the bundle contains pinned FFmpeg and PyAV, but not a separate
`ffprobe`, and the code had required `ffprobe` on PATH. This was a real
packaged-runtime gap, not a missing test dependency.

The follow-up source change discovers the bundle's pinned FFmpeg executable
next to its venv and falls back to its installed PyAV for duration. Using the
previous build's own Python and packages plus the follow-up source checkout
(`PYTHONPATH`), under the same restricted PATH, the production status returned
`available` with the `python -m yt_dlp` and `pyav` paths. It then acquired the
same real public Instagram post and completed local extraction: source status
`transcribed_local`, speech provider `local`, 20 archived OCR frames, no speech
or OCR error. The media bytes differed from the earlier host downloader's
selection, so the content hash also differed; the archive recorded the bytes
actually processed.

The focused tests cover PyAV duration and bundled FFmpeg discovery. The new
clean build from `0231f909ff3ff5186d84c3f128e4fe7d7a5e93ba` then confirmed
the same behavior with the app's own `nara` command, no `PYTHONPATH`, and the
same restricted PATH. It reported acquisition available and processed the
public Instagram post with local speech, 20 OCR frames and no extraction error.
Exact archive hashes and signature evidence are in
`research/NARA_PUBLICATION_2026-11-25.md`.
