FROM python:3.13.7-slim

WORKDIR /app

ARG INSTALL_FFMPEG=false

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN if [ "$INSTALL_FFMPEG" = "true" ]; then \
      apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/* ; \
    fi

RUN pip install --no-cache-dir "poetry==2.3.2"

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

COPY src ./src 
COPY entry.sh .

ENV PYTHONPATH=/app/src

RUN chmod +x entry.sh

EXPOSE 8080

ENTRYPOINT ["./entry.sh"]
