# User Service

The User Service manages user accounts and issues JSON Web Tokens (JWTs) used by authenticated API requests in the other services.

**Location:** `services/user-service/`  
**Framework:** Django + Django REST Framework + SimpleJWT  
**Database:** PostgreSQL, owned by this service  
**Gateway prefix:** `/api/users/`  
**Internal development port:** `8000` (the API Gateway is the recommended entry point)

## Responsibilities

- Register users with a username, email, and password.
- Authenticate users and return JWT access and refresh tokens.
- Return the current authenticated user's basic profile.
- Provide a health endpoint.

The custom user model makes email addresses unique. Passwords are created through Django's `create_user` method, so they are hashed rather than stored as plain text.

## API

All paths below are relative to `/api/users/`.

| Method | Path | Authentication | Purpose |
|---|---|---|---|
| GET | `health/` | Not required | Health check |
| POST | `register/` | Not required | Create an account |
| POST | `login/` | Not required | Obtain JWT access and refresh tokens |
| GET | `me/` | Bearer JWT required | Get the current user's profile |

### Register

```http
POST /api/users/register/
Content-Type: application/json
```

Request:

```json
{
  "username": "demo-user",
  "email": "demo@example.com",
  "password": "change-this-password"
}
```

The password must contain at least 8 characters. The response contains the created user fields exposed by the registration serializer; the password is write-only and is not returned.

### Login

```http
POST /api/users/login/
Content-Type: application/json
```

Request:

```json
{
  "username": "demo-user",
  "password": "change-this-password"
}
```

A successful login returns JWT `access` and `refresh` tokens. Send the access token to protected endpoints:

```http
Authorization: Bearer <access-token>
```

The current URL configuration exposes the token-pair login endpoint; a separate token-refresh URL is not currently configured.

### Current user

```http
GET /api/users/me/
Authorization: Bearer <access-token>
```

Example response:

```json
{
  "id": 1,
  "username": "demo-user",
  "email": "demo@example.com"
}
```

### Health check

```http
GET /api/users/health/
```

Example response:

```json
{
  "service": "user-service",
  "status": "ok"
}
```

## Configuration

The service reads its database settings from environment variables:

- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

See [`.env.example`](.env.example). Configure `DJANGO_SECRET_KEY` and `JWT_SIGNING_KEY` as required by the settings and shared authentication setup. Never commit real secrets.

## Run locally with Docker Compose

From the repository root:

```bash
docker compose up -d --build user-db user-service
docker compose exec user-service python manage.py migrate
docker compose logs -f user-service
```

Service names must match the root `docker-compose.yml`. For a complete environment, start the whole stack with `docker compose up -d --build`.

## Tests

```bash
docker compose run --rm user-service python manage.py test
```

## Security notes and limitations

- Use HTTPS for deployed environments and set `DEBUG=False` with explicit `ALLOWED_HOSTS`.
- Keep signing keys and database credentials outside version control.
- Services validating the same HS256 tokens must use compatible `JWT_SIGNING_KEY` configuration.
- The current configuration is for learning and local development, not a production deployment.
