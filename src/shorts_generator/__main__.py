# Builds a real, self-contained Windows executable on an actual Windows
# GitHub Actions runner (PyInstaller cannot cross-compile, so this step
# genuinely has to run on Windows -- it cannot be done from a Linux/macOS
# machine or CI runner).
#
# Trigger it either:
#   - manually: repo's "Actions" tab -> "Build Windows exe" -> "Run workflow"
#   - automatically: push a tag like "v1.0.0" (this also publishes a
#     GitHub Release with the .exe attached, ready to download)
#
# Either way, the output is downloadable from the "Actions" run's
# "Artifacts" section, or from the repo's "Releases" page for a tagged
# build -- both are the ordinary "click to download" experience.
name: Build Windows exe

on:
  workflow_dispatch: {}
  push:
    tags:
      - "v*"

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r build_tools/requirements-windows.txt

      - name: Build shorts-generator.exe
        run: python build_tools/build_exe.py

      - name: Verify FFmpeg was bundled
        run: |
          $exe = Get-Item "dist/shorts-generator.exe" -ErrorAction Stop
          $sizeMB = [math]::Round($exe.Length / 1MB, 1)
          Write-Host "dist/shorts-generator.exe is $sizeMB MB"

          # Ask the built exe itself where it thinks its bundled ffmpeg/ffprobe
          # are (this exercises the exact same lookup the real app uses at
          # runtime), then actually execute what it finds -- a file-size
          # guess isn't reliable evidence either way (PyInstaller may apply
          # UPX compression on this runner, which can shrink stripped FFmpeg
          # builds a lot without breaking them).
          $diag = & "dist/shorts-generator.exe" --print-bundled-ffmpeg
          $diag | ForEach-Object { Write-Host $_ }

          $ffmpegPath = ($diag | Where-Object { $_ -like "FFMPEG=*" }) -replace '^FFMPEG=', ''
          $ffprobePath = ($diag | Where-Object { $_ -like "FFPROBE=*" }) -replace '^FFPROBE=', ''

          if ([string]::IsNullOrEmpty($ffmpegPath) -or $ffmpegPath -eq "NONE" -or [string]::IsNullOrEmpty($ffprobePath) -or $ffprobePath -eq "NONE") {
            Write-Error "The built exe did not report a bundled ffmpeg/ffprobe (ffmpeg=$ffmpegPath ffprobe=$ffprobePath)."
            exit 1
          }

          Write-Host "Bundled ffmpeg reported at:  $ffmpegPath"
          Write-Host "Bundled ffprobe reported at: $ffprobePath"

          & $ffmpegPath -version
          if ($LASTEXITCODE -ne 0) { Write-Error "Bundled ffmpeg.exe did not run successfully."; exit 1 }

          & $ffprobePath -version
          if ($LASTEXITCODE -ne 0) { Write-Error "Bundled ffprobe.exe did not run successfully."; exit 1 }

          Write-Host "FFmpeg and FFprobe are bundled inside the .exe and run correctly."

      - name: Assemble distributable folder
        run: |
          $dist = "package/shorts-generator"
          New-Item -ItemType Directory -Force -Path "$dist/input" | Out-Null
          New-Item -ItemType Directory -Force -Path "$dist/output" | Out-Null
          New-Item -ItemType Directory -Force -Path "$dist/logs" | Out-Null
          Copy-Item "dist/shorts-generator.exe" "$dist/"
          Copy-Item "settings.ini" "$dist/"
          Copy-Item -Recurse "assets" "$dist/assets"
          Copy-Item "README.md" "$dist/"
          Copy-Item "vendor/win64/NOTICE.md" "$dist/FFMPEG-NOTICE.md"
          Copy-Item "vendor/win64/LICENSE-FFMPEG-GPLv3.txt" "$dist/"
          Compress-Archive -Path "$dist" -DestinationPath "package/shorts-generator-windows.zip"

      - uses: actions/upload-artifact@v4
        with:
          name: shorts-generator-windows
          path: package/shorts-generator-windows.zip

      - name: Publish GitHub Release (tagged builds only)
        if: startsWith(github.ref, 'refs/tags/')
        uses: softprops/action-gh-release@v2
        with:
          files: package/shorts-generator-windows.zip
