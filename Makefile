.PHONY: backend-install backend-lint backend-test-unit backend-test-integration test-up test-down \
	up down logs smoke-backend

BACKEND_DIR := backend
TEST_COMPOSE_FILE := docker-compose.test.yml
TEST_COMPOSE_PROJECT := monolith-template-test
COMPOSE_FILE := docker-compose.yml
COMPOSE_PROJECT := monolith-template

backend-install:
	cd $(BACKEND_DIR) && poetry install --with dev --no-root

backend-lint:
	cd $(BACKEND_DIR) && poetry run ruff check src tests --select E9,F63,F7

backend-test-unit:
	cd $(BACKEND_DIR) && poetry run pytest -m unit -q

test-up:
	docker compose -p $(TEST_COMPOSE_PROJECT) -f $(TEST_COMPOSE_FILE) up -d

test-down:
	docker compose -p $(TEST_COMPOSE_PROJECT) -f $(TEST_COMPOSE_FILE) down -v

backend-test-integration:
	@bash -lc 'set -euo pipefail; \
	COMPOSE_FILE="$$(pwd)/$(TEST_COMPOSE_FILE)"; \
	PROJECT_NAME="$(TEST_COMPOSE_PROJECT)"; \
	docker compose -p "$$PROJECT_NAME" -f "$$COMPOSE_FILE" down -v >/dev/null 2>&1 || true; \
	docker compose -p "$$PROJECT_NAME" -f "$$COMPOSE_FILE" up -d; \
	trap "docker compose -p \"$$PROJECT_NAME\" -f \"$$COMPOSE_FILE\" down -v" EXIT; \
	cd $(BACKEND_DIR); \
	poetry run pytest -m integration -q'

up:
	cp -n .env.example .env || true
	docker compose -p $(COMPOSE_PROJECT) -f $(COMPOSE_FILE) up -d --build

logs:
	docker compose -p $(COMPOSE_PROJECT) -f $(COMPOSE_FILE) logs -f --tail=200

down:
	docker compose -p $(COMPOSE_PROJECT) -f $(COMPOSE_FILE) down --remove-orphans

smoke-backend: backend-test-unit backend-test-integration
