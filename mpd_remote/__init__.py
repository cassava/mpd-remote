import random
import time
import sys
import logging
import traceback

from pathlib import Path
from typing import List, Dict, Union, Callable, Optional, Tuple
from termios import tcflush, TCIOFLUSH
from contextlib import contextmanager

from readchar import readkey, key

from .library import Track, Album
from .backend import Client
from .speech import Speech


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
        self._flush_seconds = 0.250

    def listen_stdin(self) -> None:
        """Listen in the main loop and dispatch events."""
        self.flush_stdin(0)
        while True:
            char = self.prompt_stdin()
            if char in self.EXIT_KEYS:
                logging.info("Goodbye.")
                break
            elif char in self._actions:
                try:
                    self._actions[char]()
                except:
                    traceback.print_exc()
                    with self.mute_context() as ctx:
                        ctx.say("Sorry, an error occurred.")
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

    def flush_stdout(self):
        sys.stderr.flush()
        sys.stdout.flush()

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

        def say_entry(index):
            ctx.say(f"{index+1}")
            entry = menu[index][0]
            if type(entry) is not str:
                entry = entry(ctx)
            return ctx.say_async(entry)

        index = 0
        while True:
            player = say_entry(index)
            self.flush_stdin(self._flush_seconds)
            char = self.prompt_stdin()

            logging.info(f"Kill process: {player.pid}")
            player.terminate()
            player.wait()

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
