import sys
import subprocess
import tempfile
from typing import Union, List, Dict
from pathlib import Path

import yaml
import mutagen
from mutagen import id3

from .library import Album


class Editable:
    genre_sep = ", "

    def __init__(self, album: Union[Album, str]):
        if isinstance(album, Album):
            self.key = str(album.path)
            self.genres = album.genres
            self.multi = album.is_multi_capable()
        else:
            self.multi = album.rfind(":") != -1
            key, _, genres = album.rpartition(self.delim)
            self.key = key.strip()
            if self.key == "":
                print(f"Error parsing: {album}")
                raise RuntimeError("cannot parse album-genre data from line")
            self.genres = {
                g.strip()
                for g in genres.split(self.genre_sep.strip())
                if g.strip() != ""
            }

    @property
    def delim(self) -> str:
        return ":" if self.multi else "="

    def print(self, padding: int, file=None):
        if file is None:
            file = sys.stdout
        file.write(
            "{0:{1}} {3} {2}\n".format(
                self.key,
                padding,
                self.genre_sep.join(self.genres),
                "=" if not self.multi else ":",
            )
        )


class EditableDatabase:
    def __init__(self, albums: Dict[str, Album]):
        self.delimiter = ", "
        self.albums: Dict[str, Album] = albums
        self.database: Dict[str, Editable] = {
            key: Editable(album) for key, album in albums.items()
        }
        self.padding: int = max([len(x) for x in self.database])

    def print_genres(self, file=None, group: bool = False):
        if file is None:
            file = sys.stdout
        if group:
            return self.print_genres_grouped(file)
        for _, alb in self.database.items():
            alb.print(self.padding, file=file)

    def print_genres_grouped(self, file=None):
        if file is None:
            file = sys.stdout
        grouped: Dict[str, Album] = dict()
        for _, alb in self.database.items():
            for genre in alb.genres:
                if genre not in grouped:
                    grouped[genre] = list()
                grouped[genre].append(alb)

        print("# vim: set ft=yaml fdm=marker:")
        print("---")
        genres = sorted(grouped, key=lambda x: len(grouped[x]), reverse=True)
        for genre in genres:
            albums = grouped[genre]
            genre_total = f" # {len(albums)} {{{{{{1"
            print(
                "\n{:{}}{}".format(
                    genre + ":",
                    self.padding - len(genre_total) + 4,
                    genre_total,
                ),
                file=file,
            )
            for album in albums:
                print(
                    "- {:{}} #{} {}".format(
                        album.key,
                        self.padding,
                        "=" if not album.multi else " ",
                        self.delimiter.join(album.genres),
                    ),
                    file=file,
                )

    def _update_album(self, item: Editable, library_dir: Path) -> bool:
        if item.key not in self.database:
            print(f"Error: cannot match album: {item.key}")
            return False
        original = self.database[item.key]
        if original.genres != item.genres:
            diff = "[{}] -> [{}]".format(
                self.delimiter.join(original.genres),
                self.delimiter.join(item.genres),
            )
            print(f"Update: {item.key} from {diff}")
            album = self.albums[item.key]
            for trck in album.tracks:
                filepath = library_dir / trck.path
                if not filepath.exists():
                    print(f"- error: file does not exist: {filepath}")
                print(f"- update: {filepath}")
                try:
                    self._update_genres(filepath, list(item.genres))
                except RuntimeError as err:
                    print(f"- error: {err}")
            return True
        return False

    def _update_genres(self, filepath: Path, genres: List[str]):
        if filepath.suffix == ".flac":
            audio = mutagen.File(filepath)
            audio["GENRE"] = genres
            audio.save()
        elif filepath.suffix == ".m4a":
            if len(genres) > 1:
                raise RuntimeError(f"cannot set multiple genres for: {filepath}")
            audio = mutagen.File(filepath)
            audio["\xa9gen"] = genres[0]
            audio.save()
        elif filepath.suffix == ".mp3":
            if len(genres) > 1:
                raise RuntimeError(f"cannot set multiple genres for: {filepath}")
            tags = mutagen.id3.ID3(filepath)
            tags.add(mutagen.id3.TCON(encoding=3, text=genres[0]))
            tags.save(filepath)
        else:
            raise RuntimeError(f"cannot set genre for: {filepath}")

    def edit_genres(self, library: Path, editor: str, group: bool = False):
        assert library.is_dir()
        from_editor: List[Editable] = list()
        if group:
            tmpfile = tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            )
            self.print_genres_grouped(tmpfile)
            tmpfile.close()

            # Let user modify file:
            subprocess.run([editor, tmpfile.name], check=True)
            return
        else:
            # Write editable state to file:
            tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
            for _, alb in self.database.items():
                alb.print(self.padding, file=tmpfile)
            tmpfile.close()

            # Let user modify file:
            subprocess.run([editor, tmpfile.name], check=True)

            # Read changes from file:
            with open(tmpfile.name, "r") as file:
                change_data = file.read()
            for line in change_data.splitlines():
                if line.startswith("#"):
                    continue
                if line.strip() == "":
                    continue
                from_editor.append(Editable(line))

        # Apply changes:
        modified = 0
        for item in from_editor:
            if self._update_album(item, library_dir=library):
                modified += 1
        return modified
