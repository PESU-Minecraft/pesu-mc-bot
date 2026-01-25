FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev
COPY . .
EXPOSE 7860
ENV WEB_CONCURRENCY=2
ENV GUNICORN_WORKERS=2
ENV GUNICORN_THREADS=2
RUN chmod +x start.sh
CMD ["./start.sh"]

