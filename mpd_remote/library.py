"""
Internal representations of the the music library and its components.
"""

import random
import logging

from pathlib import Path
from typing import List, Dict, Union, Tuple, Set

from . import vanity


class Track:
    def __init__(self, data: Dict[str, str]):
        """
        Data looks like:
        {
            'file': 'A Fine Frenzy/One Cell In The Sea/01-Come On Come Out.flac'
            'last-modified': '2021-02-22T12:11:46Z'
            'title': 'Come On Come Out'
            'artist': 'A Fine Frenzy'
            'albumartist': 'A Fine Frenzy'
            'album': 'One Cell In The Sea'
            'disc': '1'
            'date': '2008'
            'track': '1'
            'genre': 'Indie Rock'
            'time': '216'
            'duration': '215.733'
            'pos': '0'
            'id': '1'
        }
        """
        self.data = data

    @property
    def title(self) -> str:
        return self.data["title"]

    @property
    def artist(self) -> Union[str, List[str]]:
        return self.data["artist"]

    @property
    def albumartist(self) -> str:
        return self.data["albumartist"]

    @property
    def album(self) -> str:
        return self.data["album"]

    @property
    def date(self) -> str:
        return self.data["date"]

    @property
    def duration(self) -> float:
        return float(self.data["duration"])

    @property
    def genres(self) -> List[str]:
        if "genre" not in self.data:
            return []
        gnre = self.data["genre"]
        if isinstance(gnre, str):
            return [gnre]
        else:
            return gnre

    @property
    def path(self) -> Path:
        return Path(self.data["file"])

    @property
    def last_modified(self) -> str:
        return self.data["last-modified"]


class Album:
    def __init__(self, tracks: List[Track]):
        self.tracks = tracks
        self.artist = tracks[0].albumartist
        self.title = tracks[0].album
        self.date = tracks[0].date
        self.duration = sum([x.duration for x in tracks])

    def has_genre(self, genre: str) -> bool:
        for trck in self.tracks:
            if genre in trck.genres:
                return True
        return False

    def is_multi_capable(self) -> bool:
        """Return True if all tracks are capable of storing multiple tag values."""
        for trck in self.tracks:
            if trck.path.suffix in [".mp3", ".m4a", ".mp4"]:
                return False
        return True

    @property
    def genres(self) -> Set[str]:
        genres: Set[str] = set()
        for trck in self.tracks:
            for gnre in trck.genres:
                genres.add(gnre)
        return genres

    @property
    def path(self) -> Path:
        return self.tracks[0].path.parent

    @property
    def files(self) -> List[Path]:
        return [x.path for x in self.tracks]

    @property
    def newest_modified(self) -> str:
        return max([x.last_modified for x in self.tracks])

    @property
    def oldest_modified(self) -> str:
        return min([x.last_modified for x in self.tracks])


class Library:
    def __init__(self, data: List[Dict[str, str]]):
        self.errors = 0
        self.warnings = 0

        lib: Dict[str, Dict[str, List[Track]]] = dict()
        for item in data:
            # Skip playlists and directories for now
            if "file" not in item:
                continue

            # Make sure we have enough metadata to work with
            if ("albumartist" not in item and "artist" not in item) or (
                "album" not in item
            ):
                logging.error(f"Track missing artist or album: {item}")
                self.errors += 1
                continue

            # Print warnings for missing metadata:
            if "genre" not in item:
                logging.debug(f"Track missing genres: {item}")
                self.warnings += 1
            if "albumartist" not in item:
                logging.debug(f"Track missing album-artist: {item}")
                self.warnings += 1
                item["albumartist"] = item["artist"]

            art = item["albumartist"]
            alb = item["album"]
            if art not in lib:
                lib[art] = dict()
            if alb not in lib[art]:
                lib[art][alb] = list()
            lib[art][alb].append(Track(item))

        self.data = data
        self.albums: Dict[str, Album] = dict()
        self.artists: Dict[str, Dict[str, Album]] = dict()
        for art in lib.keys():
            self.artists[art] = dict()
            for alb in lib[art].keys():
                trcks = lib[art][alb]
                self._check_tracks(trcks)
                album = Album(trcks)
                self.artists[art][alb] = album
                self.albums[str(album.path)] = album

    def _check_tracks(self, tracks):
        try:
            assert len(tracks) > 0, "no tracks"
            expect = tracks[0]
            for trck in tracks:
                assert (
                    trck.albumartist == expect.albumartist
                ), "album artist inconsistent"
                assert trck.album == expect.album, "album inconsistent"
                assert trck.path.parent == expect.path.parent, "directory inconsistent"
        except AssertionError as err:
            logging.error(f"Malformed album '{tracks[0].album}': {err}")
            self.errors += 1

    def albums_with_genres(self, genres: List[str]) -> List[Album]:
        result: List[Album] = list()
        for album in self.albums.values():
            ags = album.genres
            for want in genres:
                if want in ags:
                    result.append(album)
        return result

    def random_album(self, genres: List[str] = None) -> Album:
        if genres is not None:
            albums = self.albums_with_genres(genres)
            return random.choice(albums)
        return random.choice(list(self.albums.values()))

    def recent_albums(self, limit: int = 100) -> List[Album]:
        albums = list(self.albums.values())
        albums.sort(key=lambda x: x.newest_modified)
        return albums[:limit]

    def search_vanity(self, numbers: str, mode: str = "linear"):
        regex = vanity.to_regex(numbers, mode)
        logging.info(f"Searching regex: {regex}")
        for key in self.albums.keys():
            if regex.search(key):
                logging.info(f"Search found: {key}")
                yield self.albums[key]
