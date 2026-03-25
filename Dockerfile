FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
COPY src ./src
COPY README.md ./

RUN uv sync --frozen

COPY . .

ENTRYPOINT ["uv", "run", "etl"]