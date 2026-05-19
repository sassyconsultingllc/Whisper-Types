# WhisperTyper

Always-on-top Windows bar. Records voice, transcribes with faster-whisper
(local), optionally cleans transcript via LLM, pastes into the window you pick.
Optional local TTS for read-back.

## Quick start

**From source:**
```
dev_setup.bat
run.bat
```

**Build standalone exe:**
```
build.bat           rem release (no console)
build_debug.bat     rem debug (console visible)
package.bat         rem zip dist\ for distribution
```

**Open in Visual Studio:**
Double-click `WhisperTyper.sln`. Requires Python Tools for Visual Studio (PTVS).
`main.py` is set as the startup file.

**Open in VS Code:**
Open the folder. `.vscode/launch.json` provides launch configs.

## Features

- Toggle / push-to-talk hotkey modes, plus a separate cancel hotkey
- VAD auto-stop on silence (toggle mode)
- Visualizer: bar meter, spectrogram, or off
- Pre-paste preview with editable transcript, audio stats, optional auto-send timer
- LLM cleanup via OpenAI-compatible endpoint (Ollama/LM Studio/OpenAI/Groq)
- Local TTS (Kokoro/Piper/OpenAI-compat) with Speak button + optional auto-read
- Streaming interim transcripts during long recordings
- JSONL history with copy / re-send / speak
- Per-target prefs remembered per exe

## Hotkeys (default)

- Primary: `Ctrl+Alt+Space`
- Cancel: `Ctrl+Alt+X`
- Preview: `Ctrl+Enter` send, `Esc` cancel

pynput syntax. Modifiers `<ctrl>`, `<alt>`, `<shift>`, `<cmd>`. Examples:
`<ctrl>+<alt>+<space>`, `<f9>`, `<ctrl>+<shift>+r`.

## Config locations

- `%USERPROFILE%\.whispertyper\config.json`
- `%USERPROFILE%\.whispertyper\history.jsonl`
- `%USERPROFILE%\.whispertyper\target_prefs.json`
- `%USERPROFILE%\.whispertyper\kokoro\` (TTS model cache)

## LLM cleanup endpoints

- Ollama (yomama): `http://100.99.213.97:11434/v1`, model `llama3.2:3b`
- LM Studio: `http://localhost:1234/v1`
- OpenAI: `https://api.openai.com/v1`, `gpt-4o-mini`
- Groq: `https://api.groq.com/openai/v1`, `llama-3.1-8b-instant`

## TTS backends

`pip install kokoro-onnx` - 82M params, Apache 2.0, ~330MB model auto-downloaded.

`pip install piper-tts` - tiny (~20MB) voices from rhasspy/piper-voices on HF.

`openai_compat` - any HTTP server exposing `/v1/audio/speech` (openedai-speech,
AllTalk TTS, etc).

Note: "grok-2" is xAI's chat LLM, not TTS. Kokoro is the current local TTS
leader as of late 2024 / 2025.

## Files

| File | Purpose |
|---|---|
| `main.py` | App + MiniBar |
| `audio_capture.py` | Mic capture with snapshot |
| `transcriber.py` | faster-whisper wrapper |
| `vad.py` | Streaming RMS VAD |
| `waveform.py`, `spectrogram.py` | Visualizers |
| `target.py` | Window enum + UIA injection |
| `hotkey.py` | Multi-combo hotkey |
| `preview.py` | Pre-paste dialog |
| `history.py` | JSONL store + viewer |
| `target_prefs.py` | Per-exe preferences |
| `llm.py` | OpenAI-compatible cleanup client |
| `tts.py` | Kokoro / Piper / OpenAI-compat TTS |
| `settings_dialog.py` | Tabbed settings UI |
| `WhisperTyper.sln/pyproj` | Visual Studio project |
| `whispertyper.spec` | PyInstaller release config |
| `whispertyper_debug.spec` | PyInstaller debug config |
| `build.bat`, `build_debug.bat` | PyInstaller build scripts |
| `package.bat` | Zip dist folder for distribution |
| `dev_setup.bat` | Bootstrap dev environment |
| `sassy_smoke.py` | SassyMCP smoke test |
| `SASSY_NOTES.md` | SassyMCP automation reference |
