from typing import Literal, TypedDict

type Kind = Literal["gif", "image", "video"]


class FolderPreview(TypedDict):
    thumbs: list[str]
    media: int
    subfolders: int
    partial: bool


class DirectoryListing(TypedDict):
    path: str
    name: str
    crumbs: list[dict[str, str]]
    folders: list[DirectoryFolderListing]
    items: list[DirectoryItemListing]


class DirectoryFolderListing(TypedDict):
    name: str
    path: str
    thumbs: list[str]
    media: int
    subfolders: int
    partial: bool


class DirectoryItemListing(TypedDict):
    name: str
    path: str
    kind: Kind
    size: int
    mtime: int
