# Nara wake word artifacts

The product phrase is **“Ei, Nara”**. Its acoustic model still needs training and a Portuguese
benchmark. Nara intentionally ships without a product-specific detector instead of relabeling an
unrelated acoustic model.

To enable openWakeWord, set `wake_word.openwakeword.model` to an explicit `.tflite` path after
training and validation. The model label, displayed phrase and evaluation must agree. The runtime
is provided by [pyopen-wakeword](https://github.com/rhasspy/pyopen-wakeword); code, feature-model
and detector licenses must be checked separately before redistribution.
