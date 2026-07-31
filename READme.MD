# WINGS Backend

FastAPI backend for the WINGS application.

---

## Prerequisites

- Python 3.13+
- Docker & Docker Compose
- Git

---

## Local Development Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd masterstrokebackend
```

### 2. Create and activate virtual environment

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the database

```bash
docker compose up postgres -d
```

This starts PostgreSQL on port **5440** (mapped from container port 5432).

### 5. Configure environment variables

Copy the example below into a `.env` file at the project root:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5440/wings_db

# Keycloak (optional — leave blank if not using)
KEYCLOAK_SERVER_URL=
KEYCLOAK_REALM=
KEYCLOAK_CLIENT_ID=
KEYCLOAK_CLIENT_SECRET=
KEYCLOAK_ADMIN_CLIENT_ID=
KEYCLOAK_ADMIN=
KEYCLOAK_ADMIN_PASSWORD=
KEYCLOAK_ISSUER=

# Media storage (optional — defaults to <project_root>/media)
MEDIA_ROOT=

# File upload limits
MAX_VIDEO_SIZE_MB=50
MAX_IMAGE_SIZE_MB=5

# Points config
POINTS_PER_100_INR=10

# Dev helpers
DEBUG_RETURN_OTP=false
```

### 6. Run database migrations

```bash
alembic upgrade head
```

### 7. Start the application

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8004 --reload
```

The API will be available at:

| Endpoint | URL |
|---|---|
| API Root | http://localhost:8004 |
| Interactive Docs (Swagger) | http://localhost:8004/docs |
| Health Check | http://localhost:8004/ready |

---

## Docker Setup (Full Stack)

Runs PostgreSQL + Keycloak + Backend together.

```bash
docker compose up --build
```

The backend will be available at **http://localhost:8000**.

To run only specific services:

```bash
# Database only
docker compose up postgres -d

# Database + Keycloak
docker compose up postgres keycloak -d
```

To stop all services:

```bash
docker compose down
```

---

## Database Connection Details

| Setting | Value |
|---|---|
| Host | `localhost` |
| Port | `5440` |
| Database | `wings_db` |
| Username | `postgres` |
| Password | `postgres` |
| Connection String | `postgresql://postgres:postgres@localhost:5440/wings_db` |

---

## Project Structure

```
masterstrokebackend/
├── app/
│   ├── main.py          # FastAPI app entry point
│   ├── config.py        # Settings (loaded from .env)
│   ├── database.py      # Database engine & session
│   ├── models/          # SQLAlchemy models
│   ├── routers/         # API route handlers
│   ├── services/        # Business logic
│   ├── deps/            # FastAPI dependencies
│   └── utils/           # Utility helpers
├── alembic/             # Database migrations
├── scripts/             # Utility scripts
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Common Commands

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```
