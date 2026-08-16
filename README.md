# Home Shine Backend

Production-oriented FastAPI backend for Home Shine. Phase 1 delivers the platform foundation only: configuration, PostgreSQL migrations, authentication, authorization, logging, request IDs, health checks, Docker, and tests.

## Local development

1. Copy `.env.example` to `.env` and set strong development secrets.
2. Start the API and PostgreSQL: `docker compose up --build`.
3. Apply migrations: `docker compose exec api alembic upgrade head`.

The API is available at `http://localhost:8000`; documentation at `/docs` in development. Health checks are `/health` and `/health/ready`.

Public registration creates CUSTOMER accounts only. A phone number is mandatory; email is optional and unique when supplied.

## First owner account

After migrations, set the `BOOTSTRAP_OWNER_*` values in your local `.env`, then run `python scripts/bootstrap_owner.py`. The command refuses to run if an owner already exists. Remove those variables immediately after the first owner is created.
