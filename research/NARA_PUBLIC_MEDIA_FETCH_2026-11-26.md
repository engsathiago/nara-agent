# Public media acquisition check — 2026-11-26

The Learning Fabric now has a public URL entry point through an optional,
installed `yt-dlp`. The command restricts the input to supported HTTPS video
hosts, ignores user configuration and browser cookies, selects one video, sets
a 500 MB download ceiling, and validates the resulting file with `ffprobe`
before archiving it. The same archived source is used by local STT and frame
OCR. The temporary download directory is removed after ingestion.

The extractor options follow the project's [official yt-dlp
documentation](https://github.com/yt-dlp/yt-dlp/blob/master/README.md).

## Real local check

On this macOS machine with `yt-dlp 2026.08.19`, the production
`fetch_public_media` function acquired the user's public Instagram post
`https://www.instagram.com/p/DdFLWjqAfMC/` without cookies. It returned
`source:46bafd75c32053dcac9115f5eca0164bfcd4ac281efd86cf2cd870ba7882f171`:
13,443,564 bytes archived with the original post URL, and `ffprobe` accepted
the duration. The status was `needs_extraction`, as the check did not request
speech or screen OCR. This proves public acquisition and local archival for
that post at that time; it does not prove that all Instagram posts or private
saved posts can be fetched, or that the video content was understood.

A second run requested local extraction on the same real post. The public
download succeeded, macOS Vision archived 20 distinct text-bearing frame
observations, and the fused screen text had 3,816 characters. Its source
status was `screen_text_local`. The source-checkout environment had no
installed local STT backend, and the recorded error was `No installed local
STT backend is available.` The screen result was retained; speech was not
silently claimed. The previously built Desktop runtime has the optional local
Whisper dependencies, but this exact URL path has not yet been retested in a
new bundle.

A first command variant exposed two `yt-dlp` behaviors: unknown Instagram
duration was silently skipped by the metadata duration filter, and
`--max-downloads 1` returned code 101 after saving one file. The final path
uses `--no-playlist`, checks exactly one returned path, and verifies duration
with `ffprobe` on the actual downloaded bytes. Focused tests cover invalid
URLs, missing extractor, temporary cleanup, CLI integration, and rejection of
overlong media before archive creation.

Authenticated media acquisition remains separate. No browser cookies are read
by this path; a post that requires login returns a visible acquisition error.

The subsequent packaging pass pins `yt-dlp==2026.8.19` in the optional
`media-fetch` extra. The Desktop build stages all declared extras, so it can
invoke the module through its own Python interpreter when no standalone
`yt-dlp` binary is on the app's `PATH`. Source installs can add the extra or
provide the command externally. A focused test exercises that module fallback;
the actual bundled-app check is recorded with the package build, separately.
