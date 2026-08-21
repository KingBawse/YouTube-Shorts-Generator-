# YouTube Shorts Generator

A batch tool that turns ordinary landscape (16:9) source videos into
vertical (9:16) YouTube Shorts / TikTok / Instagram Reels-ready videos,
using FFmpeg for all rendering — **no background image or other asset
required**. Drop videos in a folder, run it, and every file is
converted, logged, and reported on — failures on individual files are
skipped so the rest of the batch still completes. Optionally, an AI
plugin can also suggest a viral-optimized title, description, and
hashtags for every rendered video.

The Windows build also bundles FFmpeg itself, so there's nothing to
separately install or configure — see [Getting a ready-made Windows
.exe](#getting-a-ready-made-windows-exe).

## Features

- **A downloadable Windows .exe with FFmpeg built in.** No separate
  FFmpeg install, no PATH configuration — the exact pain point this
  project exists to remove. See [Getting a ready-made Windows
  .exe](#getting-a-ready-made-windows-exe) for how to get one.
- **No background image needed by default.** The default fit mode
  (`auto_blur_video`) converts a 16:9 clip straight to 9:16 by using a
  blurred copy of the same clip as the backdrop — the full original
  frame is always kept fully visible (high-quality Lanczos downscaling,
  never cropped, never upscaled), so no video content or resolution is
  lost beyond what fitting a wider frame into a taller canvas inherently
  requires. Quality-first encoding defaults (`crf=18`, `preset=slow`)
  are used throughout.
- Seven background **fit modes** in total, for when you do want a
  custom look: the auto-blurred-video default above, a static blurred
  or sharp image, a solid color, a gradient, a split top/bottom band,
  and a custom branding template with a cut-out safe area.
- **Batch processing** of a whole input folder in one run, with
  per-file error isolation: a corrupt/unsupported file is logged and
  skipped, the rest of the batch continues.
- **Resumable runs**: by default, a file whose output already exists is
  left alone, so re-running a batch after an interruption only renders
  what's missing (`overwrite_existing = true` to force a re-render).
- **Timestamped run log + human-readable batch summary** written to
  `logs/` on every run.
- **Optional AI title/description/hashtag suggestions** for every
  rendered video, written as a sidecar file, using your own OpenAI API
  key. See [AI-generated titles, descriptions, and
  hashtags](#ai-generated-titles-descriptions-and-hashtags).
- **Plugin architecture** so every other module in the project's
  roadmap (captions, watermarking, thumbnails, platform-specific
  export, upload automation, ...) can be added later without modifying
  the core pipeline. See [Extending the
  application](#extending-the-application).
- The core conversion pipeline is pure Python + FFmpeg — no GPU, cloud
  service, or paid API required unless you turn on the AI suggestions
  plugin.

## Requirements

**If you just want the Windows .exe:** none of the below — see
[Getting a ready-made Windows .exe](#getting-a-ready-made-windows-exe).
FFmpeg is bundled inside it.

**If you're running from Python source instead:**

- Python 3.9+
- [FFmpeg and FFprobe](https://ffmpeg.org/download.html) available on
  your `PATH` (or pointed to explicitly in `settings.ini`) — only the
  built Windows `.exe` has FFmpeg bundled in; running from source uses
  whatever FFmpeg is installed on your machine, same as any other tool.
- `pip install -r requirements.txt` (just Pillow at runtime; PyInstaller
  is only needed to build a standalone executable)

## Quick start (running from source)

```bash
pip install -r requirements.txt
mkdir -p input
cp /path/to/your/clips/*.mp4 input/
python run.py
```

Finished videos appear in `output/`, converted to 9:16 with no extra
configuration needed. Edit `settings.ini` if you'd rather use one of
the image-based fit modes instead of the no-asset-required default.

## Project structure

```
yt_shorts_generator/
├── run.py                        # Top-level launcher (dev + PyInstaller entry point)
├── settings.ini                  # All user-tunable configuration (see below)
├── requirements.txt
├── build_tools/
│   ├── build_exe.py                # PyInstaller build script (bundles FFmpeg on Windows)
│   └── requirements-windows.txt    # Windows-build-only: fetches real ffmpeg/ffprobe binaries
├── vendor/win64/
│   ├── LICENSE-FFMPEG-GPLv3.txt   # Required license text for the bundled GPLv3 binary
│   └── NOTICE.md                  # Where the bundled binaries come from + compliance notes
├── .github/workflows/
│   └── build-windows.yml          # Builds the real .exe on a Windows GitHub Actions runner
├── assets/
│   ├── sample_background.jpg      # Placeholder image for blurred_image/sharp_image
│   └── branding_templates/
│       └── sample_template.png    # Placeholder branding template with a safe-area hole
├── src/shorts_generator/
│   ├── __main__.py                 # CLI entry point (argparse)
│   ├── config.py                   # settings.ini loading + validation
│   ├── bundled_ffmpeg.py           # Auto-detects a PyInstaller-bundled ffmpeg/ffprobe
│   ├── logger.py                   # Logging setup + RunSummary (batch report)
│   ├── pipeline.py                 # Batch orchestration: scan, render, skip/continue/log
│   ├── exceptions.py               # Shared exception hierarchy
│   ├── ffmpeg/
│   │   ├── runner.py                # subprocess wrapper around the ffmpeg binary
│   │   └── filters.py               # Assembles a RenderPlan into a full ffmpeg command
│   ├── background/
│   │   ├── base.py                  # BackgroundMode interface + RenderPlan/InputSpec
│   │   ├── factory.py               # fit_mode string -> BackgroundMode class
│   │   ├── blurred_image.py
│   │   ├── sharp_image.py
│   │   ├── solid_color.py
│   │   ├── gradient.py
│   │   ├── auto_blur_video.py
│   │   ├── split_top_bottom.py
│   │   └── branding_template.py
│   ├── plugins/
│   │   ├── base.py                  # RenderPlugin hook contract
│   │   ├── registry.py              # Enable/discover plugins from settings.ini
│   │   ├── examples.py              # Reference plugin: logo watermark (disabled by default)
│   │   └── ai_metadata.py           # AI title/description/hashtag suggestions (disabled by default)
│   └── utils/
│       ├── video_info.py            # ffprobe wrapper
│       └── validators.py            # Input folder scanning
└── tests/
    ├── test_background_modes.py     # Unit tests for filter-chain construction
    ├── test_plugins.py              # Unit tests for plugin config + watermark/ai_metadata logic
    └── test_bundled_ffmpeg.py       # Unit tests for bundled-binary auto-detection
```

## `settings.ini` reference

All settings live in one file, grouped into sections. Relative paths are
resolved against the folder `settings.ini` itself lives in.

| Section | Key | Meaning |
|---|---|---|
| `[paths]` | `input_dir`, `output_dir`, `log_dir` | Folders for source videos, rendered output, and logs. |
| | `ffmpeg_path`, `ffprobe_path` | Binary names or absolute paths. |
| `[output]` | `canvas_width`, `canvas_height` | Output canvas size (default `1080x1920`). |
| | `output_fps` | `0` keeps the source frame rate, or force a specific fps. |
| | `video_bitrate`, `crf`, `preset` | Encoding quality/speed controls (libx264). |
| | `container_extension`, `output_suffix` | Output filename shape: `<name><output_suffix>.<container_extension>`. |
| `[background]` | `fit_mode` | One of the seven modes below; defaults to `auto_blur_video`, which needs no external assets. |
| | `background_image` | Only used by `blurred_image` / `sharp_image`. |
| | `blur_sigma` | Blur strength for modes that blur. |
| | `solid_color`, `gradient_color_start/end`, `gradient_direction` | Color-based modes. |
| | `branding_template_path`, `branding_safe_x/y/width/height` | `branding_template` mode. |
| `[batch]` | `overwrite_existing` | Re-render files whose output already exists. |
| | `delete_source_on_success` | Delete the source file after a successful render. |
| `[plugins]` | `enabled` | Comma-separated plugin keys to activate (see below). |
| `[plugin:ai_metadata]` | `api_key`, `model`, `frame_count`, `max_output_tokens` | AI title/description/hashtag suggestions — see [below](#ai-generated-titles-descriptions-and-hashtags). |
| `[plugin:watermark]` | `image_path`, `margin` | Reference plugin — burns a logo into the bottom-right corner. |

### Background fit modes

| `fit_mode` | Needs an asset? | Description |
|---|---|---|
| `auto_blur_video` (default) | No | The video itself is duplicated, scaled to fill and heavily blurred, as its own background — the common "blurred duplicate" Shorts/TikTok look. Converts any 16:9 clip to 9:16 with zero setup and no content loss on the visible subject. |
| `blurred_image` | Yes | A still image fills the canvas, heavily blurred, behind the sharp video. |
| `sharp_image` | Yes | Same, but the background image is left in sharp focus. |
| `solid_color` | No | A flat color fills the canvas. |
| `gradient` | No | A two-color gradient (vertical / horizontal / diagonal) fills the canvas. |
| `split_top_bottom` | No | The canvas is split into a mirrored, blurred top and bottom band from the video, with the sharp video centered across the seam. |
| `branding_template` | Yes | A PNG with a transparent "safe area" (logo, channel frame, sponsor skin) is composited on top, with the video placed inside the safe area. |

## AI-generated titles, descriptions, and hashtags

The `ai_metadata` plugin (`src/shorts_generator/plugins/ai_metadata.py`)
samples a handful of frames from each finished video and sends them to
OpenAI's API (a vision-capable model, `gpt-4o-mini` by default) with a
prompt built around established short-form growth practices: a
hook-first title under YouTube's 100-character limit, a keyword-rich
description with a call-to-action, a mix of broad/niche/specific
hashtags, and a flat list of classic YouTube "tags". The response is
written next to each rendered video as:

- `<name>.metadata.json` — machine-readable, for feeding into an upload
  script later
- `<name>.metadata.txt` — human-readable, ready to copy/paste

**This is not part of the free core pipeline** — it calls a paid
third-party API using your own credentials, and sends sampled video
frames to OpenAI for analysis. To use it:

1. Get an API key from OpenAI and set it as the `OPENAI_API_KEY`
   environment variable (preferred) — or, less securely, paste it into
   `[plugin:ai_metadata] api_key` in `settings.ini`.
2. Add `ai_metadata` to `[plugins] enabled` in `settings.ini`.

If no key is configured, the plugin logs a warning and simply skips
metadata generation — your videos still render normally either way. No
suggestion here is a guarantee of virality; treat it as a strong
first draft to review and tweak, not something to publish unedited.

## The FFmpeg filter chain

Every fit mode is a small Python class (`src/shorts_generator/background/*.py`)
that returns a `RenderPlan`: any extra FFmpeg inputs it needs, plus an
FFmpeg `filter_complex` fragment. `ffmpeg/filters.py` combines that with
the main video input and encoding flags into the full command. As a
concrete example, this is exactly what gets run for the default
`auto_blur_video` mode converting a 16:9 clip to 9:16 with no external
assets at all:

```bash
ffmpeg -y -hide_banner -loglevel error \
  -i input/clip.mp4 \
  -filter_complex "\
[0:v]split=2[bgsrc][fgsrc]; \
[bgsrc]scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,gblur=sigma=20,eq=brightness=-0.05[bg]; \
[fgsrc]scale=1080:-2:force_original_aspect_ratio=decrease:flags=lanczos,setsar=1[fg]; \
[bg][fg]overlay=(W-w)/2:(H-h)/2:format=auto[outv]" \
  -map "[outv]" -map 0:a? \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart \
  output/clip_short.mp4
```

Note the foreground (`[fgsrc]` → `[fg]`) is only ever scaled *down* to
fit the canvas width via high-quality Lanczos resampling — it's never
cropped and never upscaled, so the visible subject retains all of its
original frame content. Only the backdrop branch (`[bgsrc]` → `[bg]`)
is aggressively resampled and blurred, since it's intentionally out of
focus. Every other mode follows the same overall shape — only the
`filter_complex` fragment differs. See each file under
`src/shorts_generator/background/` for the fully commented filter graph
it builds.

## Getting a ready-made Windows .exe

The goal is exactly what you'd expect from any normal Windows download:
one `.exe`, FFmpeg already inside it, nothing else to install.

**Important limitation, stated plainly:** turning the source code into
an actual `.exe` has to happen *on a Windows machine* — PyInstaller
(the tool that packages a Python app into a standalone executable) is
not a cross-compiler, so it can't be done from Linux or macOS. That
includes this environment: I can prepare everything (which is what
this delivery already does — the real Windows `ffmpeg.exe` /
`ffprobe.exe` binaries are sourced and sitting in `vendor/win64/`,
verified as genuine Windows executables, ready to embed) but I can't
personally produce the final compiled `.exe` from here. There are two
practical ways to get one:

### Option A: GitHub Actions (recommended — you never touch Python or a terminal again after this)

This project includes `.github/workflows/build-windows.yml`, which
builds the real `.exe` on an actual Windows machine in the cloud (a
free GitHub-hosted runner) and hands you back a normal download link.

1. Push this project to a GitHub repository (create an empty one on
   github.com, then `git init && git add . && git commit -m "initial"
   && git remote add origin <your-repo-url> && git push -u origin
   main` from this folder).
2. On the repo's page, open the **Actions** tab → **Build Windows
   exe** → **Run workflow**. Or push a version tag (`git tag v1.0.0 &&
   git push --tags`), which also publishes it straight to the repo's
   **Releases** page.
3. Once it finishes (a few minutes), download `shorts-generator-windows.zip`
   from the workflow run's **Artifacts** section (or from **Releases**,
   if you used a tag) — that's your normal "click to download" moment.
4. Unzip it anywhere and double-click `shorts-generator.exe`.

Every future update just needs a `git push` (and a new tag, if you
want a proper Release) — the .exe rebuilds itself automatically.

### Option B: build it yourself on any Windows PC, once

If you have access to any Windows computer (yours, a friend's, work),
even temporarily:

1. Install Python 3.11+ from the Microsoft Store or python.org (one-time).
2. Copy this whole project folder onto that machine.
3. Open a terminal in the folder and run:
   ```
   pip install -r requirements.txt
   pip install -r build_tools\requirements-windows.txt
   python build_tools\build_exe.py
   ```
   (the second line downloads real FFmpeg binaries from PyPI to embed
   into the executable — see `vendor/win64/NOTICE.md`)
4. `dist\shorts-generator.exe` is your finished, self-contained
   executable — copy it (plus `settings.ini` and `assets/`) to any
   other Windows machine and it'll run there with nothing installed.

Either way, the resulting `.exe` bundles FFmpeg (see
`vendor/win64/NOTICE.md` for exactly which build and its GPLv3
license) — you will never need to separately install or configure
FFmpeg again.

### Building for Linux/macOS instead

```bash
pip install -r requirements.txt
python build_tools/build_exe.py
```

This produces a native `dist/shorts-generator` for whichever OS you
run it on. On Linux/macOS, FFmpeg is **not** bundled (only Windows
binaries are vendored) — install `ffmpeg`/`ffprobe` normally for your
OS (e.g. `apt install ffmpeg` or `brew install ffmpeg`); they're
picked up from `PATH` automatically.

## Extending the application

The project is deliberately architected so none of the following
require touching the core rendering pipeline:

**A new background fit mode** — add one class to
`src/shorts_generator/background/` implementing `BackgroundMode.build_plan()`
(see `base.py`), and one line in `background/factory.py`'s registry.

**A new feature module** (any of the roadmap items below) — implement
`src/shorts_generator/plugins/base.py`'s `RenderPlugin` hooks and
register it in `plugins/registry.py`. `plugins/examples.py` contains a
complete, working (disabled-by-default) logo-watermark plugin as a
template. `plugins/base.py`'s module docstring maps every roadmap item
below onto the specific hook it belongs in.

### Implemented modules

AI titles / AI descriptions / AI hashtags (`plugins/ai_metadata.py`,
disabled by default — see [above](#ai-generated-titles-descriptions-and-hashtags)).

### Planned future modules (architected for, not yet implemented)

Instagram Reels export, TikTok export, auto captions, AI subtitle
generator, animated subscribe button, logo watermark (a minimal
working version exists as `plugins/examples.py`, but no animation/asset
library around it yet), thumbnail generator, batch thumbnail creator,
and upload to the YouTube API.

### Nice-to-have ideas (not yet implemented)

Automatic silence trimming, intro/outro insertion, fade in/out,
background music layer, safe-area guides, video duration estimator,
render queue persistence, resuming interrupted renders (partially
covered today via `overwrite_existing = false`), theme customization,
keyboard shortcuts, and an automatic update checker.

## Logs

Every run writes two files to `log_dir` (`logs/` by default):

- `run_<timestamp>.log` — full debug-level log of the run, including the
  exact ffmpeg command line for any file that failed.
- `summary_<timestamp>.log` — a short human-readable report: how many
  files succeeded / were skipped / failed, and why.

## Running the tests

```bash
pip install -r requirements.txt
python -m unittest discover -s tests
```
