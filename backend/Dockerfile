FROM python:3.13.7-slim

# NOTE: for alpine use this line
# RUN apk add --no-cache bash

WORKDIR /app

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN pip install --no-cache-dir "poetry==2.3.2"

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

COPY src ./src 
COPY entry.sh .

ENV PYTHONPATH=/app/src

RUN chmod +x entry.sh

EXPOSE 8080

ENTRYPOINT ["./entry.sh"]
