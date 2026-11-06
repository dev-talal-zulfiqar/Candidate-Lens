# Dev-oriented image: installs the app editable and runs with --reload,
# matching the local (non-Docker) workflow in the README rather than a
# production build. Source is bind-mounted over this in compose.yaml, so
# the COPY here only needs to be enough for the image to build and for
# `pip install -e .` to succeed on its own.
FROM python:3.12-slim

WORKDIR /app

# psycopg[binary] and pymupdf ship prebuilt wheels for this platform, so no
# compiler toolchain is needed here.
COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir -e .

COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
