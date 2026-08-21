"""
Unit tests for bundled-binary auto-detection (see bundled_ffmpeg.py).

These simulate a "frozen" PyInstaller process by monkeypatching
``sys.frozen`` / ``sys.executable`` / ``sys._MEIPASS`` -- no actual
PyInstaller build is needed to test the resolution logic itself.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from shorts_generator.bundled_ffmpeg import find_bundled_binary


class BundledFfmpegTests(unittest.TestCase):
    def setUp(self):
        self._had_frozen = hasattr(sys, "frozen")
        self._old_frozen = getattr(sys, "frozen", None)
        self._old_executable = sys.executable
        self._had_meipass = hasattr(sys, "_MEIPASS")
        self._old_meipass = getattr(sys, "_MEIPASS", None)

    def tearDown(self):
        if self._had_frozen:
            sys.frozen = self._old_frozen
        elif hasattr(sys, "frozen"):
            del sys.frozen
        sys.executable = self._old_executable
        if self._had_meipass:
            sys._MEIPASS = self._old_meipass
        elif hasattr(sys, "_MEIPASS"):
            del sys._MEIPASS

    def test_returns_none_when_not_frozen(self):
        if hasattr(sys, "frozen"):
            del sys.frozen
        self.assertIsNone(find_bundled_binary("ffmpeg"))

    def test_finds_binary_next_to_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe_dir = Path(tmp)
            (exe_dir / "ffmpeg.exe").write_bytes(b"fake")
            fake_exe = exe_dir / "shorts-generator.exe"
            fake_exe.write_bytes(b"fake")

            sys.frozen = True
            sys.executable = str(fake_exe)
            if hasattr(sys, "_MEIPASS"):
                del sys._MEIPASS

            found = find_bundled_binary("ffmpeg")
            self.assertEqual(found, str(exe_dir / "ffmpeg.exe"))

    def test_finds_binary_in_meipass_onefile_dir(self):
        with tempfile.TemporaryDirectory() as exe_tmp, tempfile.TemporaryDirectory() as mei_tmp:
            fake_exe = Path(exe_tmp) / "shorts-generator.exe"
            fake_exe.write_bytes(b"fake")
            (Path(mei_tmp) / "ffprobe.exe").write_bytes(b"fake")

            sys.frozen = True
            sys.executable = str(fake_exe)
            sys._MEIPASS = mei_tmp

            found = find_bundled_binary("ffprobe")
            self.assertEqual(found, str(Path(mei_tmp) / "ffprobe.exe"))

    def test_returns_none_when_frozen_but_nothing_bundled(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_exe = Path(tmp) / "shorts-generator.exe"
            fake_exe.write_bytes(b"fake")

            sys.frozen = True
            sys.executable = str(fake_exe)
            if hasattr(sys, "_MEIPASS"):
                del sys._MEIPASS

            self.assertIsNone(find_bundled_binary("ffmpeg"))


if __name__ == "__main__":
    unittest.main()
