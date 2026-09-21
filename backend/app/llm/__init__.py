"""Choosing a model.

`LLM_MODE` picks one of three things, and they are genuinely different:

* `mock` never reaches this module at all - it replays a recorded game.
* `fake` runs the whole real pipeline against `FakeLLM`, spending nothing.
* `live` is Vertex AI.
"""

from app.llm.base import LLM
from app.settings import settings


def make_llm() -> LLM:
    """The model for this mode.

    `mock` resolves to the fake rather than to Vertex. Mock games never ask
    for a model at all, so this is unreachable on the normal path - but if
    something ever does reach it, spending nothing is the right failure.
    """
    if settings.llm_mode == "live":
        from app.llm.vertex import VertexLLM

        return VertexLLM()

    from app.llm.fake import FakeLLM

    return FakeLLM()
