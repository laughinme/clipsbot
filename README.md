# Fullstack monolith application template

The app requires postgres and redis launched locally to start. I prefer keeping it all as docker containers.

You can start postgresql via docker command:
```
docker run -d --name template-pg \
-e POSTGRES_USER=postgres \
-e POSTGRES_PASSWORD=secret \
-e POSTGRES_DB=template-pg \
-p 5432:5432 \
-v template_pg_data:/var/lib/postgresql/data \
postgres:17
```

Redis can also be started the same way:

```docker run -d --name redis -p 6379:6379 redis:latest```

Next step in running preexisting migrations to create database tables and seed data in them. It can be done using alembic:

```alembic upgrade head```

After these steps you can run the app locally with uvicorn:

```uvicorn main:app --host 0.0.0.0 --port 8080 --log-level debug --reload```

---
