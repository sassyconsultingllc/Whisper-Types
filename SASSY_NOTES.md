# SassyMCP Desktop Automation Notes

Quick reference for testing WhisperTyper via Sassy's tools.

## Paths

- Source: `V:\Projects\WhisperTyper\` (suggested - VeraCrypt drive)
- Debug exe: `dist\WhisperTyper-debug\WhisperTyper-debug.exe`
- Release exe: `dist\WhisperTyper\WhisperTyper.exe`
- Config: `%USERPROFILE%\.whispertyper\config.json`
- Logs (debug build): stderr of the exe; redirect with `> log.txt 2>&1`

## Build via Sassy

```
sassy_shell command="cd /d V:\Projects\WhisperTyper && dev_setup.bat"
sassy_shell command="cd /d V:\Projects\WhisperTyper && build_debug.bat"
```

The shell interceptor blocks parameters containing "format" - none used here.

## Launch + verify

```
sassy_shell command="cd /d V:\Projects\WhisperTyper && python sassy_smoke.py debug"
sassy_screen_capture
sassy_list_windows  # filter for WhisperTyper
sassy_find_text_on_screen text="WhisperTyper"
```

## Send hotkey to running app

```
sassy_focus_window title="Notepad"           # bring target to front
sassy_hotkey keys="ctrl+alt+space"            # start recording in WhisperTyper
# (talk into mic)
sassy_hotkey keys="ctrl+alt+space"            # stop
sassy_screen_diff before=<...> after=<...>    # show inserted text
```

## Inspect UI tree of preview dialog

When the pre-paste dialog opens, use sassy_screen_ocr or read the UIA tree to
verify "Heard X.Xs ... peak ..." header and the transcript text.

## Kill cleanly

```
sassy_processes filter="WhisperTyper"
sassy_kill_process pid=<pid>
```

Or one-shot:
```
sassy_shell command="taskkill /IM WhisperTyper-debug.exe /F"
```

## Common issues

1. **First launch model download** - faster-whisper pulls ~140MB on first
   transcription. Allow 30-60s before testing.
2. **Kokoro download** - first Speak triggers ~330MB download to
   `%USERPROFILE%\.whispertyper\kokoro\`. Skip TTS tests until that completes
   or pre-stage the files.
3. **Hotkey conflict** - if `Ctrl+Alt+Space` is already bound (e.g. Slack call
   start), edit `config.json` before launch.
4. **No mic permission** - Windows mic privacy settings can block sounddevice.
   Settings -> Privacy -> Microphone -> Allow desktop apps.
5. **Tailscale IP for LLM** - default config points at `100.99.213.97:11434`
   (yomama). If that LAN is offline, LLM cleanup will time out after 20s but
   not break transcription.

## File locations on yomama

If syncing source there for cross-device dev:
- `~/projects/whispertyper/` (mirror via the bidirectional sync from V:)
- Test LLM endpoint locally with: `curl http://localhost:11434/v1/models`
