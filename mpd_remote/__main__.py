from typing import Union, Set, List
from pathlib import Path
import logging
import sys
import subprocess
import tempfile
import os

import click
import mutagen
import mutagen.id3

from mpd_remote.library import Client, Album
from mpd_remote.remotes import DenonRC1223


@click.group()
@click.pass_context
@click.version_option(
    version="0.3",
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
    "-v",
    "--verbose",
    count=True,
    help="Print more information.",
)
def main(
    ctx,
    host: str,
    port: int,
    verbose: int,
):
    """Control MPD instance with your remote control."""

    # Handle verbosity:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=level)

    # Set context object
    ctx.obj = Client(host, port)


@main.command("check")
@click.pass_obj
def check(client: Client):
    """Check the library for consistency and completeness."""
    pass


@main.command("metadata")
@click.option(
    "-m",
    "--modify",
    is_flag=True,
    help="Modify metadata in editor and update files with changes.",
)
@click.option(
    "-L",
    "--library",
    type=click.Path(dir_okay=True, file_okay=False, exists=True),
    help="Library path to files that should be modified.",
)
@click.option(
    "--editor",
    type=click.STRING,
    default=os.getenv("EDITOR"),
    help="Editor to use when editing the metadata.",
)
@click.option(
    "-d",
    "--delimiter",
    type=click.STRING,
    required=True,
    default=", ",
    help="Delimiter to separate multi-field tags by.",
)
@click.option(
    "-u",
    "--update",
    is_flag=True,
    help="Update MPD library before processing metadata.",
)
@click.pass_obj
def metadata(
    client: Client,
    modify: bool,
    library: str,
    editor: str,
    delimiter: str,
    update: bool,
):
    """List and edit library album metadata."""
    if modify and not library:
        raise RuntimeError("--modify flag requires --library argument")

    if update:
        print("Updating library... ")
        client.update()
        print("Library update complete.")

    class Editable:
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
                self.genres = set(
                    [
                        g.strip()
                        for g in genres.split(delimiter.strip())
                        if g.strip() != ""
                    ]
                )

        @property
        def delim(self) -> str:
            return ":" if self.multi else "="

        def print(self, padding: int):
            self.write(sys.stdout, padding)

        def write(self, file, padding: int):
            file.write(
                "{0:{1}} {3} {2}\n".format(
                    self.key,
                    padding,
                    delimiter.join(self.genres),
                    "=" if not self.multi else ":",
                )
            )

    def update_genres(filepath: Path, genres: List[str]):
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

    database = {key: Editable(album) for key, album in client.library.albums.items()}
    padding = max([len(x) for x in database])

    if not modify:
        for _, alb in database.items():
            alb.print(padding)
    if modify:
        # Write editable state to file:
        tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        for _, alb in database.items():
            alb.write(tmpfile, padding)
        tmpfile.close()

        # Let user modify file:
        subprocess.run([editor, tmpfile.name], check=True)

        # Read changes from file:
        with open(tmpfile.name, "r") as file:
            change_data = file.read()
        from_editor = list()
        for line in change_data.splitlines():
            if line.startswith("#"):
                continue
            if line.strip() == "":
                continue
            from_editor.append(Editable(line))

        # Compare changes with original
        modified = list()
        library_dir = Path(library)
        for item in from_editor:
            if item.key not in database:
                print(f"Error: cannot match album: {item.key}")
                continue
            original = database[item.key]
            if original.genres != item.genres:
                modified.append(item)
                diff = "[{}] -> [{}]".format(
                    delimiter.join(original.genres),
                    delimiter.join(item.genres),
                )
                print(f"Update: {item.key} from {diff}")
                album = client.library.albums[item.key]
                for trck in album.tracks:
                    filepath = library_dir / trck.path
                    if not filepath.exists():
                        print(f"- error: file does not exist: {filepath}")
                    print(f"- update: {filepath}")
                    try:
                        update_genres(filepath, list(item.genres))
                    except RuntimeError as err:
                        print(f"- error: {err}")
        print()
        print(f"Updated {len(modified)} albums.")


@main.command("listen")
@click.pass_obj
@click.option(
    "--prefetch",
    is_flag=True,
    help="Prefetch as many text segments as possible.",
)
def listen(client: Client, prefetch: bool):
    """Listen to keystrokes for actions."""
    remote = DenonRC1223(client)
    remote.load_config()
    remote.print_genre_groups()
    if prefetch:
        logging.info("Pre-fetching speech segments, this might take a while.")
        remote.prefetch()
    remote.listen_stdin()
