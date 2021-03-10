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

        # Fetch and (maybe) cache speech audio.
        if self.file.exists():
            logging.debug(f"Using cache: {self.file}")
            with self.file.open("rb") as file:
                self.audio = io.BytesIO(file.read())
        else:
            logging.debug(f"Fetching audio for: {self.text}")
            self.audio = io.BytesIO()
            self.gtts.write_to_fp(self.audio)
            if cache:
                if not self.cache_dir.exists():
                    logging.debug(f"Making directory: {self.cache_dir}")
                    self.cache_dir.mkdir(parents=True)
                with self.file.open("wb") as file:
                    logging.debug(f"Caching audio: {self.file}")
                    self.gtts.write_to_fp(file)

        return self

    def play_async(self) -> subprocess.Popen:
        self.prefetch(cache=True)
        logging.info(f"Speaking: {self.text}")
        proc = subprocess.Popen(
            ["play", "-q", str(self.file), "delay", "0.1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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


def conjoin(conjunction: str, xs: List[str]) -> str:
    assert len(xs) != 0
    n = len(xs)
    if n == 1:
        return xs[0]
    elif n == 2:
        return f"{xs[0]} {conjunction} {xs[1]}"
    else:
        return ", ".join(xs[:-1]) + " " + conjunction + " " + xs[-1]
