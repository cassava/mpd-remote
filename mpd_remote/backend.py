"""
Wrapper around an MPD client that uses types from the library module.
"""

import time
import random

from contextlib import contextmanager
from typing import List, Dict, Tuple

import mpd

from .library import Library, Album, Track


def with_api(func):
    """Decorate a method to use the client() context manager."""

    def wrapper(*args):
        with args[0].client() as api:
            return func(args[0], api, *args[1:])

    return wrapper


class Client:
    """Wrapper around an MPD client that just works."""

    def __init__(self, host: str = "localhost", port: int = 6600):
        self._client = mpd.MPDClient()
        self._host = host
        self._port = port

        with self.client() as api:
            self._data = api.listallinfo()
            self.library = Library(self._data)

    @contextmanager
    def client(self):
        """Return a raw connection to MPD as a context manager."""
        try:
            self._client.connect(self._host, self._port)
            yield self._client
        finally:
            self._client.close()
            self._client.disconnect()

    @with_api
    def genres(self, api) -> List[str]:
        return [g["genre"] for g in api.list("genre")]

    @with_api
    def status(self, api) -> Tuple[Dict[str, str], List[Track]]:
        # Stopped, Empty:
        #     status = {
        #       'repeat': '0',
        #       'random': '0',
        #       'single': '0',
        #       'consume': '1',
        #       'partition': 'default',
        #       'playlist': '2',
        #       'playlistlength': '0',
        #       'mixrampdb': '0.000000',
        #       'state': 'stop',
        #     }
        #     playlist = []
        #
        # Playing:
        #     status = {
        #       'audio': '44100:16:2',
        #       'bitrate': '1090',
        #       'consume': '1',
        #       'duration': '215.733',
        #       'elapsed': '153.627',
        #       'mixrampdb': '0.000000',
        #       'nextsong': '1',
        #       'nextsongid': '2',
        #       'partition': 'default',
        #       'playlist': '17',
        #       'playlistlength': '14',
        #       'random': '0',
        #       'repeat': '0',
        #       'single': '0',
        #       'song': '0',
        #       'songid': '1',
        #       'state': 'play',
        #       'time': '154:216',
        #       'volume': '100',
        #     }
        status = api.status()
        playlist = api.playlistinfo()
        return status, [Track(x) for x in playlist]

    @with_api
    def is_playing(self, api) -> bool:
        status = api.status()
        return status["state"] == "play"

    @with_api
    def play_random(self, api, genres: List[str] = None):
        album = self.library.random_album(genres)
        api.clear()
        for file in album.files:
            api.add(str(file))
        api.play()

    @with_api
    def play_recent(self, api, limit: int = 100):
        album = random.choice(self.library.recent_albums(limit))
        api.clear()
        for file in album.files:
            api.add(str(file))
        api.play()

    @with_api
    def play_album(self, api, album: Album):
        api.clear()
        for file in album.files:
            api.add(str(file))
        api.play()

    @with_api
    def play(self, api):
        api.play()

    @with_api
    def pause(self, api):
        api.pause()

    @with_api
    def toggle_playback(self, api):
        status = api.status()
        if status["state"] == "play":
            api.pause()
        else:
            api.play()

    @with_api
    def stop(self, api):
        api.stop()

    @with_api
    def prev(self, api):
        api.previous()

    @with_api
    def next(self, api):
        api.next()

    @with_api
    def seek_forward(self, api, seconds: int = 30):
        api.seekcur(f"+{seconds}")

    @with_api
    def seek_rewind(self, api, seconds: int = 30):
        api.seekcur(f"-{seconds}")

    @with_api
    def clear(self, api):
        api.clear()

    @with_api
    def shuffle(self, api):
        api.shuffle()

    @with_api
    def update(self, api):
        api.update()
        while "updating_db" in api.status():
            time.sleep(0.5)
        data = api.listallinfo()
        self.library = Library(data)

    @with_api
    def toggle(self, api, key, value):
        api.__getattribute__(key)(value)

    @with_api
    def status_replay_gain(self, api) -> str:
        return api.replay_gain_status()

    @with_api
    def toggle_replay_gain(self, api) -> str:
        toggle = {"off": "auto", "auto": "track", "track": "album", "album": "off"}
        state = api.replay_gain_status()
        new = toggle[state]
        api.replay_gain_mode(new)
        return new
