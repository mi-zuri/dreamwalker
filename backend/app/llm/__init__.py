"""Choosing a model.

`LLM_MODE` picks one of three things, and they are genuinely different:

* `mock` never reaches this module at all - it replays a recorded game.
* `fake` runs the whole real pipeline against `FakeLLM`, spending nothing.
* `live` is Vertex AI.
"""

from app.llm.base import LLM
from app.settings import settings


def make_llm() -> LLM:
    if settings.llm_mode == "fake":
        from app.llm.fake import FakeLLM

        return FakeLLM()

    from app.llm.vertex import VertexLLM

    return VertexLLM()
