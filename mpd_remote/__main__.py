from typing import Union, Set
import logging
import sys
import os
from pathlib import Path

import click

from .library import Client
from .remotes import DenonRC1223
from .organize import EditableDatabase


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
    "-g",
    "--group",
    is_flag=True,
    help="Group albums by genre.",
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
    group: bool,
    update: bool,
):
    """List and edit library album metadata."""
    if modify and not library:
        raise RuntimeError("--modify flag requires --library argument")

    if update:
        print("Updating library... ")
        client.update()
        print("Library update complete.")

    database = EditableDatabase(client.library.albums)
    if not modify:
        database.print_genres(group=True)
    if modify:
        modified = database.edit_genres(Path(library), editor, group)
        print(f"\nUpdated {modified} albums.")


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
