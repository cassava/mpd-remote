from typing import Callable, Optional, List
import logging
import sys
import subprocess
import os

import click
from readchar import key

from mpd_remote import Remote, Speech, MuteContext, conjoin
from mpd_remote.library import Client, Album
from mpd_remote import vanity


class DenonRC1223(Remote):
    def __init__(self, client: Client):
        super().__init__(client)
        self._repeat_char = "+"
        self._seek_seconds = 30
        self._genres = {
            "1": ["Classical"],
            "2": ["Acoustic", "Soft Rock"],
            "3": ["Folk", "Indie", "Alternative"],
            "4": ["Hip-Hop", "Rap", "Reggae"],
            "5": ["Jazz", "Instrumental"],
            "6": ["Metal", "Ska", "Punk Rock"],
            "7": ["Pop", "Rock", "Country", "Latin"],
            "8": ["Electronic", "Dance", "Disco"],
            "9": ["Worship", "Lobpreis"],
            "0": None,
        }
        self._vanity_idx = 0
        self._actions = {
            #
            # System controls:
            "~": self.power,
            #
            # Playback controls:
            " ": self.toggle_playback,
            "<": self.prev,
            ">": self.next,
            "/": self.stop,
            ",": self.seek_rewind,
            ".": self.seek_forward,
            #
            # Direction pad:
            "\r": self.enter,
            "\n": self.enter,
            key.ESC: self.back,
            key.UP: self.up,
            key.LEFT: self.left,
            key.DOWN: self.down,
            key.RIGHT: self.right,
            #
            # Center remote:
            "i": self.info,
            "s": self.source,
            "q": self.queue,
            "m": self.mode,
            "t": self.setup,
            #
            # Number pad:
            "1": self.number("1"),
            "2": self.number("2"),
            "3": self.number("3"),
            "4": self.number("4"),
            "5": self.number("5"),
            "6": self.number("6"),
            "7": self.number("7"),
            "8": self.number("8"),
            "9": self.number("9"),
            "0": self.number("0"),
            "+": self.number_plus,
            #
            # Lower row:
            "l": self.clear,
            "r": self.random,
            "p": self.repeat,
            "d": self.dimmer,
        }

    def _button(self, name: str):
        logging.info(f"Button: {name}")

    def _search_mode(self) -> str:
        return vanity.MODES[self._vanity_idx]

    def prefetch(self):
        # Prefetch common terms (these will change from time to time):
        logging.info("Prefetching: common terms")
        for text in [
            "OK",
            "Back.",
            "Not implemented yet.",
            "Use directional buttons.",
            #
            # Help: enter()
            "Press a button for help.",
            "Sorry, this button is undocumented.",
            "Sorry, this input event is unmapped.",
            #
            # Power menu: power()
            "Power menu.",
            "Update library?",
            "Updating library.",
            "Restart system?",
            "Restarting system.",
            "Shutdown system?",
            "Shutting down system.",
            #
            # Setup menu: setup()
            "Setup menu.",
            "consume: on",
            "consume: off",
            "random: on",
            "random: off",
            "repeat: on",
            "repeat: off",
            "single: on",
            "single: off",
            "single: one shot",
            "replay-gain: off",
            "replay-gain: auto",
            "replay-gain: track",
            "replay-gain: album",
            #
            # Information: info(), source(), queue()
            "Currently playing:",
            "Current playlist is empty.",
            "Current playlist has:",
            #
            # Searching: down()
            "Search albums.",
            "Searching with:",
            "search mode: strict",
            "search mode: linear",
            "search mode: fuzzy",
            "Use vanity numbers to search.",
            "Use numbers and directional buttons.",
        ]:
            Speech(text).prefetch()

        # Prefetch help texts:
        logging.info("Prefetching: help texts")
        for key in self._actions.keys():
            action = self._actions[key]
            if action.__doc__:
                Speech(action.__doc__).prefetch()

        # Prefetch numbers up to 100:
        logging.info("Prefetching: numbers")
        for num in range(100):
            Speech(f"{num}").prefetch()

        # Prefetch all album paths:
        logging.info("Prefetching: album paths")
        for alb in self._client.library.albums.keys():
            Speech(alb).prefetch()

    def power(self):
        """Update, restart or shutdown system."""
        self._button("POWER")

        def power_update(ctx):
            ctx.say("Updating library.")
            self._client.update()
            ctx.say("Done.")

        def power_restart(ctx):
            ctx.say("Restarting system.")
            subprocess.run(["reboot"])

        def power_shutdown(ctx):
            ctx.say("Shutting down system.")
            subprocess.run(["shutdown"])

        with self.mute_context() as ctx:
            self.navigate_menu(
                ctx,
                [
                    ("Update library?", power_update),
                    ("Restart system?", power_restart),
                    ("Shutdown system?", power_shutdown),
                ],
                title="Power menu.",
            )

    def toggle_playback(self):
        """Toggle playback."""
        self._button("PLAY/PAUSE")
        self._client.toggle_playback()

    def play(self):
        """Start playback."""
        self._button("PLAY")
        self._client.play()

    def pause(self):
        """Pause playback."""
        self._button("PAUSE")
        self._client.pause()

    def prev(self):
        """Previous track."""
        self._button("PREV")
        self._client.prev()

    def next(self):
        """Next track."""
        self._button("NEXT")
        self._client.next()

    def stop(self):
        """Stop playback."""
        self._button("STOP")
        self._client.stop()

    def seek_rewind(self):
        """Rewind track."""
        self._button("REWIND")
        self._client.seek_rewind(self._seek_seconds)

    def seek_forward(self):
        """Fast-forward track."""
        self._button("FORWARD")
        self._client.seek_forward(self._seek_seconds)

    def enter(self):
        """Help. In menus: selecting entries."""
        self._button("ENTER")
        with self.mute_context() as ctx:
            self.help_menu(ctx)

    def up(self):
        """Search playlists by name. In menus: previous entry."""
        self._button("UP")
        with self.mute_context() as ctx:
            ctx.say("Not implemented yet.")
        pass

    def left(self):
        """Nothing. In menus: go back."""
        self._button("LEFT")

    def down(self):
        """Search albums by path. In menus: next entry."""
        self._button("DOWN")

        play: Optional[Album] = None

        def toggle_vanity(ctx: MuteContext):
            self._vanity_idx = (self._vanity_idx + 1) % len(vanity.MODES)
            return ctx.say_async(f"search mode: {self._search_mode()}")

        def extend_results(ctx):
            if ctx.generator is None:
                return
            try:
                item = next(ctx.generator)
            except StopIteration:
                pass
            else:
                ctx.results.append(item)
                ctx.index += 1

        def say_current(ctx, say_initial: bool = False):
            if ctx.index >= 0:
                if ctx.index > 0 or say_initial:
                    ctx.player = ctx.say_async(f"{ctx.index+1}")
                result = Speech(str(ctx.results[ctx.index].path)).prefetch()
                ctx.player.wait()
                return result.play_async()
            return ctx.say_async("0")

        def new_search(ctx, query: str):
            ctx.results = []
            logging.info(f"Searching vanity: {query}")
            ctx.generator = ctx.api.library.search_vanity(
                query, mode=self._search_mode()
            )
            ctx.index = -1
            extend_results(ctx)
            if ctx.player:
                ctx.player.wait()
            return say_current(ctx)

        with self.mute_context() as ctx:
            # Set up context:
            ctx.generator = None
            ctx.results: List[Album] = []
            ctx.index: int = -1
            ctx.player: subprocess.Popen = ctx.say_async("Search albums.")

            # Build query and update results:
            query: str = ""
            while True:
                self.flush_stdin(0)
                char = self.prompt_stdin()

                logging.info(f"Kill process: {ctx.player.pid}")
                ctx.player.terminate()
                ctx.player.wait()

                if char in self.BACK_KEYS:
                    ctx.say("Back.")
                    break
                elif (char >= "0" and char <= "9") or char in ["l", "m"]:
                    if char == "l":
                        query = query[:-1]
                    elif char == "m":
                        ctx.player = toggle_vanity(ctx)
                    else:
                        query += char
                    ctx.player = new_search(ctx, query)
                elif char == "i":
                    if query != "":
                        ctx.player = ctx.say_async("Searching with:")
                        target = Speech(f"{query}").prefetch(cache=False)
                        ctx.player.wait()
                        target.play()
                    else:
                        ctx.player = ctx.say_async("Use vanity numbers to search.")
                elif char == key.DOWN:
                    if ctx.index + 1 >= len(ctx.results):
                        extend_results(ctx)
                    else:
                        ctx.index += 1
                    ctx.player = say_current(ctx)
                elif char == key.UP:
                    if ctx.index > 0:
                        ctx.index -= 1
                    ctx.player = say_current(ctx, say_initial=True)
                elif char in [key.RIGHT, "\r", "\n"]:
                    play = ctx.results[ctx.index]
                    ctx.say("OK")
                    break
                else:
                    ctx.player = ctx.say_async("Use numbers and directional buttons.")

        if play is not None:
            logging.info(f"Playing album: {play.path}")
            self._client.play_album(play)

    def right(self):
        """Nothing. In menus: select or toggle."""
        self._button("RIGHT")

    def back(self):
        """Nothing. In menus: go back."""
        self._button("BACK")

    def info(self):
        """Speak title and artist of current track."""
        self._button("INFO")
        with self.mute_context() as ctx:
            if ctx.status["playlistlength"] == "0":
                ctx.say("Current playlist is empty.")
                return
            player = ctx.say_async("Currently playing:")
            current = ctx.current()
            assert current is not None
            target = Speech(f"{current.title} by {current.artist}").prefetch(
                cache=False
            )
            player.wait()
            target.play()

    def source(self):
        """Speak album and artist of current track."""
        self._button("SOURCE")
        with self.mute_context() as ctx:
            if ctx.status["playlistlength"] == "0":
                ctx.say("Current playlist is empty.")
                return
            player = ctx.say_async("Currently playing:")
            current = ctx.current()
            assert current is not None
            target = Speech(f"{current.album} by {current.albumartist}").prefetch()
            player.wait()
            target.play()

    def queue(self):
        """Speak queue length and duration."""
        self._button("QUEUE")
        with self.mute_context() as ctx:
            if ctx.status["playlistlength"] == "0":
                ctx.say("Current playlist is empty.")
                return
            player = ctx.say_async("Current playlist has:")
            tracks = ctx.status["playlistlength"]
            minutes = round(sum([t.time for t in ctx.playlist]) / 60)
            target = Speech(f"{tracks} summing {minutes} minutes.").prefetch(
                cache=False
            )
            player.wait()
            target.play()

    def mode(self):
        """Reserved."""
        self._button("MODE")
        with self.mute_context() as ctx:
            ctx.say("Not implemented yet.")
        pass

    def setup(self):
        """Modify playback settings."""
        self._button("SETUP")

        def option(key: str):
            if key == "single":
                info = {"0": "off", "1": "on", "oneshot": "one shot"}
                toggle = {"0": "1", "1": "oneshot", "oneshot": "0"}
            else:
                info = {"0": "off", "1": "on"}
                toggle = {"0": "1", "1": "0"}
            return (
                lambda ctx: f"{key}: {info[ctx.status[key]]}",
                lambda ctx: ctx.api.toggle(key, toggle[ctx.status[key]]) or True,
            )

        def option_replay_gain():
            return (
                lambda ctx: f"replay-gain: {ctx.api.status_replay_gain()}",
                lambda ctx: ctx.api.toggle_replay_gain() or True,
            )

        with self.mute_context() as ctx:
            self.navigate_menu(
                ctx,
                [
                    option("consume"),
                    option("random"),
                    option("repeat"),
                    option("single"),
                    option_replay_gain(),
                ],
                title="Setup menu.",
            )

    def number(self, num: str) -> Callable[[], None]:
        """Create a function to play a random album from a list of genres."""
        genres = self._genres[num]
        button = f"{num} {vanity.VANITY_MAP[num]}"

        def func():
            self._button(button)
            self._repeat_char = self._input_char
            self._client.play_random(genres)

        # Set the documentation on the function so that the help function works.
        func.__doc__ = f"Play {conjoin('or', genres or ['random'])} album."
        return func

    def number_plus(self):
        """Play recent album."""
        self._button("+10 a/A")
        self._client.play_recent()
        self._repeat_char = self._input_char

    def clear(self):
        """Clear playlist."""
        self._button("CLEAR")
        self._client.clear()

    def random(self):
        """Play random album."""
        self._button("RANDOM")
        self._actions["0"]()

    def repeat(self):
        """Repeat last number choice."""
        self._button("REPEAT")
        self._actions[self._repeat_char]()

    def dimmer(self):
        """Reserved."""
        self._button("DIMMER")
        with self.mute_context() as ctx:
            ctx.say("Not implemented yet.")
        pass


@click.command()
@click.version_option(
    version="0.2",
    help="Show program version.",
)
@click.option(
    "--host",
    type=click.STRING,
    default="localhost",
    help="MPD hostname or IP address.",
)
@click.option(
    "--port",
    type=click.INT,
    default=6600,
    help="MPD port.",
)
@click.option(
    "--prefetch",
    is_flag=True,
    help="Prefetch as many text segments as possible.",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Print more information.",
)
def main(
    host: str,
    port: int,
    prefetch: bool,
    verbose: int,
):
    """Control MPD instance with your remote control."""

    # Handle verbosity:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=level)

    # Start default remote
    client = Client(host, port)
    remote = DenonRC1223(client)
    if prefetch:
        logging.info("Pre-fetching speech segments, this might take a while.")
        remote.prefetch()
    remote.listen_stdin()
