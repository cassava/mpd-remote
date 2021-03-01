from __future__ import annotations

import random
import time
import sys
import hashlib
import subprocess
import io
import logging

from pathlib import Path
from typing import List, Dict, Union, Callable, Optional, Tuple
from termios import tcflush, TCIOFLUSH
from contextlib import contextmanager

import appdirs
from gtts import gTTS
from readchar import readkey, key

from .library import Client, Track, Album

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


class MuteContext:
    """MuteContext can be used to mute the currently playing audio
    so that you can speak to the user."""

    def __init__(self, api: Client):
        self.api = api
        self.resume = False
        self.update()

    def update(self):
        self.status, self.playlist = self.api.status()

    def is_stopped(self) -> bool:
        return self.status["state"] == "stop"

    def current(self) -> Optional[Track]:
        if not self.is_stopped():
            return self.playlist[int(self.status["song"])]
        elif self.playlist:
            return self.playlist[0]
        else:
            return None

    def say(self, msg: str, cache: bool = True):
        Speech(msg, cache=cache).play()

    def say_async(self, msg: str):
        return Speech(msg).play_async()

    def __enter__(self):
        logging.debug("Entering mute context.")
        if self.status["state"] == "play":
            self.resume = True
            self.api.pause()
        return self

    def __exit__(self, type, value, traceback):
        logging.debug("Exiting mute context.")
        if self.resume:
            self.api.play()


class Remote:
    """Remote is a super-class supporting basic remote functionality."""

    EXIT_KEYS = [key.CTRL_C, key.CTRL_D]
    BACK_KEYS = EXIT_KEYS + ["\x7f", "b"]
    PREV_KEYS = BACK_KEYS + [key.LEFT]
    ENTER_KEYS = ["\r", "\n", key.RIGHT]

    def __init__(self, mpd_client):
        self._client = mpd_client
        self._actions: Dict[str, Callable[None, []]] = dict()
        self._input_char = None
        self._flush_seconds = 0.1

    def listen_stdin(self) -> None:
        """Listen in the main loop and dispatch events."""
        while True:
            char = self.prompt_stdin()
            if char in self.EXIT_KEYS:
                logging.info("Goodbye.")
                break
            elif char in self._actions:
                self._actions[char]()
            else:
                self._unbound(char)

            # Flush stdin to ignore double presses
            self.flush_stdin(self._flush_seconds)

    def prompt_stdin(self, timeout: float = 0) -> str:
        logging.info(f"Listening...")
        self._input_char = readkey()
        logging.info(f"Event: {repr(self._input_char)}")
        return self._input_char

    def flush_stdin(self, seconds: float):
        self._input_char = None
        time.sleep(seconds)
        tcflush(sys.stdin, TCIOFLUSH)

    def mute_context(self) -> MuteContext:
        return MuteContext(self._client)

    def help_menu(self, ctx: MuteContext):
        player = ctx.say_async("Press a button for help.")
        while True:
            self.flush_stdin(self._flush_seconds)
            char = self.prompt_stdin()

            logging.info(f"Kill process: {player.pid}")
            player.terminate()
            player.wait()

            if char in self.BACK_KEYS:
                ctx.say("Back.")
                break
            if char in self._actions:
                action = self._actions[char]
                if action.__doc__:
                    player = ctx.say_async(action.__doc__)
                else:
                    player = ctx.say_async("Sorry, this button is undocumented.")
            else:
                player = ctx.say_async("Sorry, this input event is unmapped.")

    def navigate_menu(
        self,
        ctx: MuteContext,
        menu: List[
            Tuple[
                Union[str, Callable[[MuteContext], str]],
                Callable[[MuteContext], Optional[bool]],
            ]
        ],
        title: Optional[str] = None,
        end_with: Optional[str] = None,
    ):
        if title is not None:
            ctx.say(title)

        index = 0
        while True:
            ctx.say(str(index + 1))
            entry = menu[index][0]
            if type(entry) is not str:
                entry = entry(ctx)
            player = ctx.say_async(entry)
            self.flush_stdin(self._flush_seconds)
            char = self.prompt_stdin()
            player.kill()
            if char in self.PREV_KEYS:
                ctx.say("Back.")
                break
            elif char == key.DOWN:
                index = (index + 1) % len(menu)
            elif char == key.UP:
                index = (index - 1) % len(menu)
            elif char in self.ENTER_KEYS:
                remain = menu[index][1](ctx)
                if remain:
                    # Update ctx
                    ctx.update()
                    continue
                if end_with:
                    ctx.say(end_with)
                break
            else:
                ctx.say("Use directional buttons.")

    def _unbound(self, char: str):
        logging.info(f"Unbound: {char}")


def conjoin(conjunction: str, xs: List[str]) -> str:
    assert len(xs) != 0
    n = len(xs)
    if n == 1:
        return xs[0]
    elif n == 2:
        return f"{xs[0]} {conjunction} {xs[1]}"
    else:
        return ", ".join(xs[:-1]) + " " + conjunction + " " + xs[-1]
