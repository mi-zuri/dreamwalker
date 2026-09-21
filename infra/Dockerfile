# One image, both halves of the product.
#
# Firebase Hosting in front of a Cloud Run backend would be the usual shape,
# but Hosting's rewrites drop the WebSocket upgrade and the music socket is
# not optional - so the API serves the built frontend itself and everything
# stays same-origin. No CORS, no second deploy target, no cross-origin token.

# ── The frontend ────────────────────────────────────────────────────────
FROM oven/bun:1.3.13-alpine AS web

WORKDIR /src
COPY package.json bun.lock ./
COPY web/package.json web/package.json
RUN bun install --frozen-lockfile

COPY web web
# `tsc && vite build` - a type error fails the image rather than shipping.
RUN cd web && bun run build

# ── The backend ─────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS app

# Bytecode up front, no venv indirection, no stray writes at runtime.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dependencies resolve from the lockfile in their own layer, so a code change
# does not reinstall the world.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/app app
COPY --from=web /src/web/dist /app/static

ENV PATH="/app/.venv/bin:$PATH" \
    STATIC_DIR=/app/static \
    PORT=8080

# Cloud Run owns the port, so it is read at start rather than baked in.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
