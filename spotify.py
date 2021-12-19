import datetime
from typing import Any
import dataclasses

import aiohttp
import base64

JSON = dict[str, str] | dict[str, int] | dict[str, bool] | dict[str, float]
JSON |= list[JSON] | dict[str, JSON]


class Timer:
    def __init__(self, min=0, sec=0, ms=0):
        self.expire_time = datetime.datetime.now() + datetime.timedelta(minutes=min, seconds=sec, milliseconds=ms)

    def has_expired(self):
        return datetime.datetime.now() > self.expire_time


@dataclasses.dataclass(frozen=True)
class Artist:
    followers: int
    genres: list[str]
    id: str
    name: str
    popularity: int

    def __eq__(self, other):
        return self.id == other.id

    @staticmethod
    def from_dict(init_dict: JSON):
        return Artist(followers=init_dict.get('followers'),
                      genres=init_dict.get('genres'),
                      id=init_dict.get('id'),
                      name=init_dict.get('name'),
                      popularity=init_dict.get('popularity'))


@dataclasses.dataclass(frozen=True)
class Song:
    id: str
    name: str
    artist_ids: list[str]
    popularity: int

    def __eq__(self, other):
        return self.id == other.id

    @staticmethod
    def from_dict(init_dict: JSON):
        return Song(id=init_dict.get('track').get('id'),
                    name=init_dict.get('track').get('name'),
                    artist_ids=[artist.get('id') for artist in init_dict.get('track').get('artists')],
                    popularity=init_dict.get('track').get('popularity'))


class SimpleSpotifyAPI:
    def __init__(self, client_id: str, client_secret: str, session: aiohttp.ClientSession):
        self.client_id = client_id
        self.client_secret = client_secret
        self.session = session
        self.user_auth_token = ""
        self.auth_timer = Timer(0)

    async def authenticate(self):
        encoded_auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("ascii")
        ).decode("ascii")
        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": 'client_credentials'
        }
        res = await self.session.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
        res.raise_for_status()
        res_json = await res.json()

        self.auth_timer = Timer(res_json['expires_in'])
        self.user_auth_token = res_json["access_token"]

    async def spot_req(self, url: str, params: Any | None = None, data: Any | None = None):
        if self.auth_timer.has_expired():
            await self.authenticate()

        headers = {
            "Authorization": f"Bearer {self.user_auth_token}",
            "Content-Type": "application/json",
            "Accepts": "application/json"
        }
        return await self.session.get(url, headers=headers, params=params, data=data)

    async def get_user_playlists(self, user_id) -> list[JSON]:
        req_res = await self.spot_req(f"https://api.spotify.com/v1/users/{user_id}/playlists")
        playlists_json = await req_res.json()

        return playlists_json['items']

    async def get_playlist_items(self, playlist_id: str, page: int = 0) -> dict[JSON]:
        params = {
            "limit": "100",
        }
        if page > 0:
            params['offset'] = f"{page * 100}"
        req_res = await self.spot_req(f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks", params=params)
        items_json = await req_res.json()

        return items_json
    
    async def get_related_artists(self, artist_id: str) -> list[Artist]:
        req_res = await self.spot_req(f"https://api.spotify.com/v1/artists/{artist_id}/related-artists")
        related_artists_json = await req_res.json()

        return [Artist.from_dict(artist_json) for artist_json in related_artists_json['artists']]
