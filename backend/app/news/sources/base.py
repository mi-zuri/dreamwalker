"""What a news source has to be.

A source is anything that can produce `Article`s without a model call. That is
the whole interface, and it is deliberately narrow: collection is the free
part of the pipeline, and it stays free by having nowhere to put a model.
"""

from typing import Protocol

from app.models.game import Region
from app.news.models import Article


class NewsSource(Protocol):
    name: str
    region: Region

    async def fetch(self) -> list[Article]:
        """Everything this source is currently offering. Failures raise."""
        ...
