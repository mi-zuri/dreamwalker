"""Where generated images live.

Content-addressed by the prompt that produced them, which ports the old
`server/src/services/cache.ts` idea: the same prompt is never paid for twice.
That matters more than it sounds, because an image is a flat $0.0336 whatever
its resolution, so the only lever on image cost is how many are generated.

Two backends. `memory` keeps bytes in this process and serves them from
`/api/media/asset/...`, which is correct locally and wrong behind more than
one Cloud Run instance. `gcs` writes to the assets bucket and hands back a
public URL.
"""

import asyncio
import hashlib
import logging
from typing import Protocol

from app.settings import settings

log = logging.getLogger(__name__)

PNG = "image/png"


def asset_key(prompt: str, suffix: str = ".png") -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:32] + suffix


class AssetStore(Protocol):
    async def put(self, key: str, data: bytes, content_type: str = PNG) -> str:
        """Stores the bytes and returns the URL the client should load."""
        ...

    async def get(self, key: str) -> tuple[bytes, str] | None: ...

    async def url_for(self, key: str) -> str | None:
        """The URL for an already-stored asset, or `None` if it is not there."""
        ...


class MemoryAssets:
    def __init__(self) -> None:
        self._blobs: dict[str, tuple[bytes, str]] = {}

    async def put(self, key: str, data: bytes, content_type: str = PNG) -> str:
        self._blobs[key] = (data, content_type)
        return f"/api/media/asset/{key}"

    async def get(self, key: str) -> tuple[bytes, str] | None:
        return self._blobs.get(key)

    async def url_for(self, key: str) -> str | None:
        return f"/api/media/asset/{key}" if key in self._blobs else None


class GcsAssets:
    def __init__(self, bucket: str) -> None:
        from google.cloud import storage  # imported late: local runs never need it

        self._bucket = storage.Client().bucket(bucket)
        self._name = bucket

    def _public(self, key: str) -> str:
        return f"https://storage.googleapis.com/{self._name}/{key}"

    async def put(self, key: str, data: bytes, content_type: str = PNG) -> str:
        def write() -> None:
            blob = self._bucket.blob(key)
            blob.cache_control = "public, max-age=31536000, immutable"
            blob.upload_from_string(data, content_type=content_type)

        await asyncio.to_thread(write)
        return self._public(key)

    async def get(self, key: str) -> tuple[bytes, str] | None:
        def read() -> tuple[bytes, str] | None:
            blob = self._bucket.blob(key)
            if not blob.exists():
                return None
            return blob.download_as_bytes(), blob.content_type or PNG

        return await asyncio.to_thread(read)

    async def url_for(self, key: str) -> str | None:
        exists = await asyncio.to_thread(lambda: self._bucket.blob(key).exists())
        return self._public(key) if exists else None


_store: AssetStore | None = None


def get_assets() -> AssetStore:
    global _store
    if _store is None:
        if settings.assets_mode == "gcs" and settings.assets_bucket:
            _store = GcsAssets(settings.assets_bucket)
        else:
            if settings.assets_mode == "gcs":
                log.warning("ASSETS_MODE=gcs but ASSETS_BUCKET is unset; using memory")
            _store = MemoryAssets()
    return _store


def reset_assets() -> None:
    """Test hook; the store is a process-wide singleton."""
    global _store
    _store = None
