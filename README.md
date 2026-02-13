# Pralapin Backend

FastAPI server: API logic, JWT auth, MongoDB (Beanie), S3, FCM, and CCTV signed URLs.

## Setup

```bash
cd backend
uv sync   # or: pip install -e .
cp .env.example .env
# Edit .env with MongoDB, AWS, Firebase, etc.
```

## MongoDB (required)

The backend needs MongoDB on `localhost:27017`. Start it in one of these ways:

- **Docker:** From project root: `docker compose up -d mongodb`
- **Homebrew (macOS):** `brew services start mongodb-community` (after `brew install mongodb-community`)

## Run

```bash
uv run uvicorn app.main:app --reload --port 8000
```

## Collections

- **users** – RBAC (Admin, Teacher, Parent)
- **students** – Child info, class, attendance logs
- **activities** – Daily logs, lesson progress, photo metadata (S3)
- **billing** – Fee structures, payment status, receipt PDFs (S3)
- **branches** – Locations, CCTV stream configs
- **feed** – Announcements (FCM on publish)

## API

- `POST /api/auth/login`, `POST /api/auth/register`, `GET /api/auth/me`
- `GET/POST /api/users`, `/api/students`, `/api/activities`, `/api/billing`, `/api/branches`, `/api/feed`
- `GET /api/cctv/stream-url` – Signed HLS URL (school hours, parent validation)
- `POST /api/attendance/mark` – Mark attendance, notify parent
