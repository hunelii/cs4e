# A container is a recipe for a machine, written down.
#
# Read it top to bottom: it starts from a known Linux with a known Python, adds
# exactly the dependencies in the lock file, copies the code in, and says what
# to run. Nothing about your laptop is involved, which is the entire point --
# this is the answer to "but it works on my machine".

FROM python:3.12-slim

# uv is the same tool you used on day 1. Copying the binary from its own image
# is faster and more reproducible than downloading an installer at build time.
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first, code second. Docker caches each step, and the code
# changes far more often than the dependency list -- so this ordering means
# editing metrics.py rebuilds in a second instead of a minute.
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-install-project --no-dev

COPY src/ ./src/
COPY dashboard/ ./dashboard/
COPY data/raw/ ./data/raw/
RUN uv sync --no-dev

# Where the API looks for the export inside the container. Nothing here knows
# or cares what the path was on the machine that built it.
ENV FACTORYFLOW_DATA=/app/data/raw/line_a_2026-03.csv
ENV PATH="/app/.venv/bin:$PATH"

# Documentation, not a firewall: EXPOSE tells a reader which port matters. The
# port only actually opens when you map it with -p.
EXPOSE 8000

# 0.0.0.0, not 127.0.0.1. Inside the container, "localhost" means the container
# itself, so binding there makes the service unreachable from outside it. This
# is the single most common first-container mistake.
CMD ["uvicorn", "factoryflow.api:app", "--host", "0.0.0.0", "--port", "8000"]
