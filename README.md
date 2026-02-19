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
uv run uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
```

Use `--host 0.0.0.0` when testing the mobile app on a physical device so the backend accepts connections from your network.

## Push notifications (FCM)

Announcements (and attendance/homework) trigger push notifications to the parent app when:

1. **Firebase is configured** – In `.env`, set `FIREBASE_CREDENTIALS_PATH` to the **absolute or relative path** of your Firebase project’s **service account JSON** (e.g. `./pralapin-firebase-adminsdk.json`). Download it from Firebase Console → Project settings → Service accounts → “Generate new private key”.
2. **Parents have registered a device** – Each parent must open the **mobile app while logged in** at least once so their FCM token is sent to the backend (`POST /api/auth/fcm-token`). After that, they will receive pushes when you create an announcement (or mark attendance, add homework).

If pushes don’t appear, check backend logs after creating an announcement: you’ll see either “Firebase not configured”, “no FCM tokens found”, or “Announcement push: success=…”.

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
