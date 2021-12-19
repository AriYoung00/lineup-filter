import math
import os

import aiohttp
import asyncio
from rich import table, tree
from rich.layout import Layout, Panel
from rich import console
from rich import traceback

import artists
from spotify import SimpleSpotifyAPI, JSON, Artist, Song

traceback.install()

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")

c = console.Console()


def intersect_lineup_with_songs(lineup: list[str], playlist_items: list[JSON]) -> dict[Artist, list[Song]]:
    lineup = [artist.lower() for artist in lineup]
    artist_song_dict: dict[Artist, list[Song]] = {}
    for song_json in playlist_items:
        song = Song.from_dict(song_json)
        for artist_json in song_json['track']['artists']:
            artist = Artist.from_dict(artist_json)
            if artist.name.lower() in lineup:
                if artist in artist_song_dict:
                    artist_song_dict[artist].append(song)
                else:
                    artist_song_dict[artist] = [song]

    return artist_song_dict


async def intersect_lineup_with_related_artists(lineup: list[str], artist_list: list[Artist],
                                                spot: SimpleSpotifyAPI) -> dict[Artist, list[Artist]]:
    lineup = [artist.lower() for artist in lineup]

    related_artist_lists = list(await asyncio.gather(
        *(spot.get_related_artists(artist.id) for artist in artist_list)
    ))
    for i, related_artists in enumerate(related_artist_lists):
        related_artist_lists[i] = list(filter(lambda a: a.name.lower() in lineup and a not in artist_list,
                                              related_artists))

    output_dict: dict[JSON, list[JSON]] = {}
    for i, artist in enumerate(artist_list):
        output_dict[artist] = related_artist_lists[i]

    return output_dict


def print_playlists(playlists: list[JSON]):
    t = table.Table(title="Playlists")
    t.add_column("#")
    t.add_column("Name")
    t.add_column("ID")
    i = 1
    for item in playlists:
        t.add_row(f"{i}", item['name'], item['id'])
        i += 1
    c.print(t)


def print_artists_with_songs(artist_song_dict: dict[Artist, list[Song]]):
    t = table.Table("Artist", table.Column("Songs", no_wrap=True), title="Common Artists")
    for artist in artist_song_dict.keys():
        first_row = True
        for song in artist_song_dict[artist]:
            if first_row:
                t.add_row(f"[bold]{artist.name}[/]", song.name)
                first_row = False
            else:
                t.add_row("", song.name)
        if artist != list(artist_song_dict.keys())[-1]:
            t.add_row("")

    c.print(t)


def print_related_artists_tree(related_artists_dict: dict[Artist, list[Artist]]):
    related_tree = tree.Tree("Related Artists")
    for artist in related_artists_dict.keys():
        artist_branch = related_tree.add(f"[bold orange]{artist.name}[/]")
        for related in related_artists_dict[artist]:
            artist_branch.add(related.name)

    c.print(related_tree)


async def main():
    async with aiohttp.ClientSession() as session:
        # Instantiate SimpleSpotifyAPI
        spot = SimpleSpotifyAPI(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, session)
        await spot.authenticate()

        # Display user's playlists
        user_id = os.environ.get("SPOTIFY_USER_ID")
        if user_id is None:
            c.print("[bold]User ID: [/]", end='')
            user_id = input()
        playlists = await spot.get_user_playlists(user_id)
        print_playlists(playlists)

        # Get playlist number
        c.print("[bold]Playlist #: ", end='')
        pl_num = int(input()) - 1  # prints with offset index

        # Get playlist items
        playlist_id = playlists[pl_num]['id']
        song_list = []
        items = await spot.get_playlist_items(playlist_id)
        song_list.extend(items['items'])
        num_pages = math.ceil(items['total'] / items['limit'])
        if num_pages > 1:
            pages = await asyncio.gather(
                *(spot.get_playlist_items(playlist_id, i) for i in range(1, num_pages + 1))
            )
            for page in pages:
                song_list.extend(page['items'])

        # Find relations
        artist_song_dict = intersect_lineup_with_songs(artists.COUNTDOWN_NYE_2021, song_list)
        related_intersection = await intersect_lineup_with_related_artists(artists.COUNTDOWN_NYE_2021,
                                                                           list(artist_song_dict.keys()), spot)

        # Display relations
        print_artists_with_songs(artist_song_dict)
        print_related_artists_tree(related_intersection)

        # layout = Layout()
        # layout.split_row(
        #     Layout(t2),
        #     Layout(related_tree)
        # )
        f = console.Console(record=True)
        f.save_html("artist-extract-output.html")
        input()


if __name__ == '__main__':
    asyncio.run(main())
