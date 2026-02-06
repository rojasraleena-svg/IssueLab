---
name: video-quality-audit
description: Audit generated video quality with objective checks and produce an optimization plan for next render iteration.
---

# Video Quality Audit

Use this skill after rendering and before final publishing.

## Goal
Evaluate output video quality with reproducible checks, then provide focused optimization actions.

## Checks
1. Metadata quality:
- inspect codec, fps, bitrate, width, height, duration using `ffprobe`.
2. Content readability:
- verify text size/readability, contrast, and pacing by sampling key timestamps.
3. Audio/visual consistency:
- ensure no frozen frames, severe stutter, or abrupt transitions.
4. Requirement match:
- compare output against issue constraints (target duration, style, language).

## Suggested Commands
- `ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,bit_rate -show_entries format=duration -of json <video.mp4>`

## Quality Gate
- Pass: technical metrics valid and visual readability acceptable.
- Warn: playable but one or more quality issues present.
- Fail: broken output, severe quality regression, or requirement mismatch.

## Output Template
## Video Quality Report
- gate: [pass|warn|fail]
- video: [path]
- metrics:
  - resolution: [e.g., 1920x1080]
  - fps: [e.g., 30]
  - duration_s: [e.g., 72.3]
  - bitrate: [value]
- findings:
  - [issue 1]
  - [issue 2]
- next_optimizations:
  - [specific action 1]
  - [specific action 2]

## References
- ffprobe Documentation: https://ffmpeg.org/ffprobe.html
- Manim output and config: https://docs.manim.community/en/stable/tutorials/output_and_config.html
- GitHub Actions artifacts: https://docs.github.com/actions/using-workflows/storing-workflow-data-as-artifacts
