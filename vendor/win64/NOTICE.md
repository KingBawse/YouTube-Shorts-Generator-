# Bundled FFmpeg binaries (Windows x86_64)

`build_tools/build_exe.py` embeds real `ffmpeg.exe` / `ffprobe.exe`
binaries directly into the built Windows executable, so it needs **no
separate FFmpeg install** — this is the whole point: FFmpeg setup
(finding the right build, unzipping it, getting it onto `PATH`) is
exactly the friction this project exists to remove.

The binaries themselves are **not stored in this repository** (they're
~80 MB each) — they're fetched at build time from PyPI via the
[`ffmpeg-binaries`](https://pypi.org/project/ffmpeg-binaries/) package
(pinned in `build_tools/requirements-windows.txt`), which republishes
the well-known [Gyan Doshi FFmpeg Windows builds](https://www.gyan.dev/ffmpeg/builds/)
(`FFmpeg version 6.0-essentials_build-www.gyan.dev`, verified at the
time this project was put together) as installable package data
specifically for this kind of bundling use case. Source:
https://github.com/MatteoH2O1999/ffmpeg-binaries

`build_exe.py` locates the installed package's `ffmpeg.exe` /
`ffprobe.exe` (via `ffmpeg.FFMPEG_PATH` / `ffmpeg.FFPROBE_PATH` from
that package) and passes them straight to PyInstaller's
`--add-binary`. Nothing about the binaries is modified.

## License

This FFmpeg build is licensed under the **GNU General Public License
v3.0** (it includes GPL-only components such as libx264/libx265) — the
full text is kept in this folder (`LICENSE-FFMPEG-GPLv3.txt`) since it
must accompany the binaries wherever they're distributed. If you build
and share this application's `.exe`, keep this license file (and this
notice) alongside it — the GitHub Actions workflow
(`.github/workflows/build-windows.yml`) does this automatically as
part of its packaged output. Corresponding source for this build is
available from the upstream projects linked above and from
https://ffmpeg.org.
