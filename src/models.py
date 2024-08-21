from typing import TypedDict


class SpammerData(TypedDict):
    api_id: int
    api_hash: str
    folders: list[str]
    proxy: list[str]
    text: str
