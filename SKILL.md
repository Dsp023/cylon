---
name: code-driven-shorts
description: Make vertical shorts (YouTube Shorts, Instagram Reels, TikTok, 720x1280) from code. A declarative script.json drives an animated HTML/SVG page, Kokoro TTS voice, dynamic kinetic captions, procedural SFX, ducked music, and real code/terminal demos; Playwright frames are piped directly to ffmpeg.
---

# Code-Driven Vertical Shorts

Turn a topic or script into a polished 60fps vertical video (720x1280) using pure code. No cameras, no manual video editing, no image model hallucinations, and zero cloud API fees.

A single declarative `script.json` configures the narration, scenes, code snippets, visual themes, and metadata. `build.py` compiles it into voice audio, procedural SFX, lo-fi background music, and timing data. Playwright renders every frame deterministically via a `setT(t)` HTML canvas/DOM function, and `ffmpeg` outputs a final MP4 with automated sidechain audio ducking.

## Project Structure

```text
.
├── SKILL.md             # Agent skill definition and runbook
├── README.md            # Repository documentation and guides
├── package.json         # Node.js dependencies (Playwright)
├── requirements.txt     # Python dependencies (kokoro-onnx, soundfile, numpy)
├── scripts/
│   ├── download_models.py # Model downloader for Kokoro TTS weights
│   ├── build.py         # TTS + timeline + captions + SFX + music generator
│   ├── snap.js          # Fast Playwright preview frame generator (QA contact sheet)
│   ├── render.js        # Playwright frame capture piped directly to ffmpeg
│   └── mux.py           # ffmpeg audio ducking, mixing, and thumbnail export
├── templates/
│   └── page.html        # Generic 720x1280 renderer exposing window.setT(t)
└── examples/
    └── demo_agent_loop/ # Ready-to-render reference project
        ├── script.json  # Complete demo configuration
        └── toy_agent.py # Sample real program executed for terminal scene
```

## Standard Workflow

When an agent or developer is asked to create a video:

1. **Write `script.json`**:
   - Aim for ~2.5 words per second. Keep scene narration concise (1–3 sentences per scene).
   - Video duration for shorts should stay between 30 and 55 seconds.
2. **Build Audio & Timeline**:
   ```bash
   python scripts/build.py --input script.json --output-dir ./dist
   ```
   - Prints total duration, scene windows, and sentence cues.
   - If total duration exceeds 55 seconds, trim the narration or set `"speed": 1.1`.
3. **Generate & Inspect Previews**:
   ```bash
   node scripts/snap.js --data ./dist/data.js --output-dir ./dist/previews
   ```
   - Renders 1 preview snapshot per scene at its cue midpoint.
   - Check layout, headline wrapping, and caption visibility before full rendering.
4. **Render Video Stream**:
   ```bash
   node scripts/render.js --data ./dist/data.js --output ./dist/tmp_short.mp4 --fps 30
   ```
   - Headless Playwright seeks `setT(t)` frame-by-frame and pipes raw RGBA frames into ffmpeg.
5. **Mux Audio & Export**:
   ```bash
   python scripts/mux.py --video ./dist/tmp_short.mp4 --audio-dir ./dist --output final.mp4
   ```
   - Normalizes voice audio (`loudnorm`), applies music sidechain compression ducking under voice, mixes SFX, extracts `thumbnail.jpg`, and writes `post_metadata.txt`.

---

## Configuration Specification (`script.json`)

```json
{
  "title": "What is an AI Agent Loop?",
  "description": "Explaining the core architecture behind autonomous AI agents.",
  "hashtags": ["#ai", "#coding", "#softwareengineering", "#techshorts"],
  "voice": "am_michael",
  "speed": 1.05,
  "theme": {
    "accent": "#ff7a50",
    "accent2": "#5aa2ff",
    "glowA": "rgba(255,122,80,0.18)",
    "glowB": "rgba(90,162,255,0.15)"
  },
  "scenes": [
    {
      "type": "hook",
      "say": "An AI agent is not magic. It is just a loop.",
      "title": ["An AI agent", "is just a <i>loop.</i>"],
      "sub": "// agent architecture 101"
    },
    {
      "type": "loop",
      "say": "Every cycle has five steps: Goal, Think, Act, Observe, and Done.",
      "title": "The <i>Core Loop</i>",
      "nodes": ["Goal", "Think", "Act", "Observe", "Done"]
    },
    {
      "type": "code",
      "say": "In code, it is literally a while loop calling a model with tool definitions.",
      "title": "The Whole <i>Idea</i>",
      "lines": [
        "while not task.is_done():",
        "    plan = model.think(task, history)",
        "    tool_call = model.decide_action(plan)",
        "    result = execute_tool(tool_call)",
        "    history.append(result)"
      ],
      "hl": [[0, 1, 2, 3, 4], [1], [2], [3], [4]]
    },
    {
      "type": "terminal",
      "say": "Watch the agent execute tools in real time. It tests code, catches errors, and self-corrects.",
      "title": "Real <i>Execution</i>",
      "command": "python toy_agent.py",
      "note": "deterministic agent · real environment"
    },
    {
      "type": "cards",
      "say": "To make it reliable, you need three guardrails: timeout bounds, memory pruning, and approval gates.",
      "title": ["Essential", "<b>Guardrails</b>"],
      "cards": [
        ["01", "Max Iterations", "Prevent infinite run loops and cost explosion", "--a"],
        ["02", "Context Pruning", "Summarize tool outputs to avoid token overflow", "--b"],
        ["03", "Approval Gates", "Require user confirmation before destructive actions", "--a"]
      ]
    },
    {
      "type": "cta",
      "say": "Stop writing brittle scripts. Start building autonomous agent loops.",
      "title": ["Now Build", "<i>Your Own</i>"],
      "sub": "// run the code on GitHub",
      "pills": ["Think", "Act", "Observe"]
    }
  ]
}
```

---

## Built-In Scene Types

| Scene Type | Purpose | Key Attributes | Visual Sync Behavior |
| :--- | :--- | :--- | :--- |
| `hook` | Grabs viewer attention in the first 3 seconds | `title`, `sub` | Kinetic text scale & ambient radial glow pulse |
| `loop` | Animated architecture / state cycle | `nodes`, `title` | Orbiting glow token travels SVG path; nodes light up on sentence cues |
| `code` | Shows code implementation | `lines`, `hl` | Syntax-highlighted code; lines dim/brighten per cue index `hl[k]` |
| `terminal` | Real program terminal run | `command`, `output`, `note` | Lines reveal progressively; passes highlighted in green, errors in red |
| `cards` | 2–3 structured bullet points / takeaways | `cards` | Cards pop in sequentially with SFX dings on each sentence cue |
| `stats` | Big numbers / metric comparisons | `stat`, `label`, `delta` | Number counter ticks up to target value during scene |
| `cta` | Channel branding / call-to-action | `title`, `sub`, `pills` | Interactive-styled tag pills pop in with glowing finish |

---

## Audio Pipeline

- **TTS Voice (`vo.wav`)**:
  - Powered by Kokoro-82M ONNX model locally.
  - Voices: `am_michael` (male American), `af_heart` (female American), `bm_george` (male British), `bf_emma` (female British).
  - Sentences are split on punctuation for accurate segment timestamps and sentence-level cue triggers.
- **SFX (`sfx.wav`)**:
  - Procedurally generated via `numpy` at 44.1 kHz (no audio assets required):
    * `whoosh`: Low-pass filtered noise frequency sweep for scene transitions.
    * `ding`: Dual-sine harmonic chime (1568 Hz + 3136 Hz) for cards and node highlights.
    * `tick`: Sharp click transient for code reveals.
- **Background Music (`music.wav`)**:
  - Procedurally synthesized lo-fi pad: Am-F-C-G progression at 90 BPM with soft pluck arpeggios.
- **Audio Ducking**:
  - ffmpeg `sidechaincompress` filter reduces music volume whenever narration is active.

---

## Production Quality Checklist

- [ ] Duration is between 30 and 55 seconds.
- [ ] Headlines wrap nicely (max ~18 characters per line on mobile).
- [ ] No visual elements overlap the caption zone (`top: 980px` to `1150px`).
- [ ] Real demo outputs are generated from actual script execution.
- [ ] Preview contact sheet (`snap.js`) visually verified before full render.
- [ ] Audio volume levels: voice around -16 LUFS, background music ducked cleanly.

