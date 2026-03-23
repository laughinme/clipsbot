FROM python:3.13.7-slim

WORKDIR /app

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN pip install --no-cache-dir "poetry==2.3.2"

COPY pyproject.toml ./
RUN poetry install --only main --no-root

COPY src ./src

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "main"]
