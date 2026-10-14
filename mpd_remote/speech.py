from __future__ import annotations

import io
import hashlib
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Union, Callable, Optional, Tuple

import appdirs
from gtts import gTTS


CACHE_DIR = Path(appdirs.user_cache_dir("mpd-remote", None))


class Speech:
    def __init__(self, text: str, cache: bool = True):
        self.text: str = text
        self.lang: str = "en"
        self.hash: str = hashlib.md5(text.encode("utf-8")).hexdigest()
        self.audio: Optional[io.BytesIO] = None
        self.cache: bool = cache

    @property
    def file(self) -> Path:
        return self.cache_dir / Path(self.hash + ".mp3")

    @property
    def cache_dir(self) -> Path:
        return CACHE_DIR / Path("tts")

    @property
    def gtts(self) -> gTTS:
        return gTTS(self.text, lang=self.lang)

    def prefetch(self, cache: bool = None) -> Speech:
        # Fallback to class default if cache is unset
        if cache is None:
            cache = self.cache

        # If we already have audio data, then ignore request.
        if self.audio is not None:
            return self

        if self.file.exists():
            logging.debug(f"Using cache: {self.file}")
            self.audio = io.BytesIO(self.file.read_bytes())
            return self

        logging.debug(f"Fetching audio for: {self.text}")
        buf = io.BytesIO()
        self.gtts.write_to_fp(buf)  # raises on failure, before anything touches disk
        self.audio = buf

        if cache:
            self._write_cache()
        return self

    def _write_cache(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_bytes(self.audio.getvalue())
        tmp.replace(self.file)  # atomic rename
        logging.debug(f"Cached audio: {self.file}")

    def play_async(self) -> subprocess.Popen:
        self.prefetch(cache=True)
        if not self.file.exists():
            self._write_cache()

        self.prefetch(cache=True)
        logging.info(f"Speaking: {self.text}")
        proc = subprocess.Popen(
            ["play", "-q", str(self.file), "delay", "0.1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        logging.info(f"Process: {proc.pid}")
        return proc

    def play(self) -> None:
        self.prefetch()
        assert self.audio is not None
        logging.info(f"Speaking: {self.text}")
        with subprocess.Popen(
            ["play", "-q", "-t", "mp3", "-", "delay", "0.1"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            close_fds=True,
        ) as proc:
            stdout, _ = proc.communicate(self.audio.getvalue())
            if proc.returncode != 0:
                raise RuntimeError(f"error running play:\n{stdout.decode()}")


class Beep:
    def __init__(self, hz: int = 300, duration: float = 0.2):
        self.hz = hz
        self.duration = duration

    def play(self) -> None:
        logging.info(f"Beeping: {self.hz} Hz for {self.duration} s.")
        with subprocess.Popen(
            [
                "play",
                "-q",
                "-n",
                "-c1",
                "synth",
                str(self.duration),
                "sine",
                str(self.hz),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            close_fds=True,
        ) as proc:
            stdout, _ = proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"error running play:\n{stdout.decode()}")


def conjoin(conjunction: str, xs: List[str]) -> str:
    assert len(xs) != 0
    n = len(xs)
    if n == 1:
        return xs[0]
    elif n == 2:
        return f"{xs[0]} {conjunction} {xs[1]}"
    else:
        return ", ".join(xs[:-1]) + " " + conjunction + " " + xs[-1]
