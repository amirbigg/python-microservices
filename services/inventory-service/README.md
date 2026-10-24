# Inventory Service

The Inventory Service is the authoritative owner of available stock and reservation state. Other services should use its API rather than reading or writing its database directly.

**Location:** `services/inventory-service/`  
**Framework:** Django REST Framework  
**Database:** PostgreSQL, owned by this service  
**Messaging:** RabbitMQ consumer for `product.created`  
**Gateway prefix:** `/api/inventory/`  
**Internal development port:** `8003`

## Responsibilities

- Store available quantity for each Catalog product ID.
- Expose authenticated read-only inventory endpoints.
- Reserve stock for an order item.
- Release a reservation and return its quantity to available stock.
- Confirm a reservation, keeping the quantity deducted.
- Initialize inventory records from Catalog's `product.created` event.

Inventory records reference Catalog products by numeric `product_id`; there is no cross-service database foreign key.

## Data model

### Inventory item

- `product_id`: unique positive integer identifying a Catalog product.
- `quantity`: available quantity.
- `created`, `updated`: timestamps.

### Stock reservation

- `reservation_id`: UUID supplied by the caller and unique across reservations.
- `product_id`: represented by the related inventory item's product ID.
- `quantity`: quantity reserved.
- `status`: `reserved`, `released`, or `confirmed`.
- `created`, `updated`: timestamps.

## API

All paths below are relative to `/api/inventory/`. Except for the health endpoint, requests require a valid JWT:

```http
Authorization: Bearer <access-token>
```

| Method | Path | Purpose |
|---|---|---|
| GET | `health/` | Health check |
| GET | `items/` | List inventory records |
| GET | `items/{product_id}/` | Retrieve a product's inventory record |
| POST | `reservations/` | Reserve stock |
| POST | `reservations/{reservation_id}/release/` | Release a reservation |
| POST | `reservations/{reservation_id}/confirm/` | Confirm a reservation |

### Check inventory

```http
GET /api/inventory/items/12/
Authorization: Bearer <access-token>
```

Example response:

```json
{
  "id": 1,
  "product_id": 12,
  "quantity": 18,
  "created": "2026-10-24T09:00:00Z",
  "updated": "2026-10-24T09:00:00Z"
}
```

### Reserve stock

```http
POST /api/inventory/reservations/
Authorization: Bearer <access-token>
Content-Type: application/json
```

```json
{
  "reservation_id": "6b7c2a8e-0d16-4f8a-92a5-5d19c7b5d4ab",
  "product_id": 12,
  "quantity": 2
}
```

The service locks the inventory row inside a database transaction, verifies available quantity, deducts the requested amount, and creates a reservation. A new reservation returns `201 Created`; a matching retry may return `200 OK`. Insufficient stock or a conflicting reuse of a reservation ID returns `409 Conflict`. A product without an inventory record returns `404 Not Found`.

A reservation ID is idempotent for the same product and quantity while its state permits it. A released reservation ID cannot be reused.

### Release or confirm

```http
POST /api/inventory/reservations/6b7c2a8e-0d16-4f8a-92a5-5d19c7b5d4ab/release/
Authorization: Bearer <access-token>
```

```http
POST /api/inventory/reservations/6b7c2a8e-0d16-4f8a-92a5-5d19c7b5d4ab/confirm/
Authorization: Bearer <access-token>
```

- **Release:** adds the reserved quantity back to available inventory and marks the reservation `released`. Releasing an already released reservation is idempotent.
- **Confirm:** marks the reservation `confirmed`; the stock remains deducted. A confirmed reservation cannot be released.
- Both endpoints return the serialized reservation. Unknown IDs return `404`; invalid state transitions return `409`.

### Health check

```http
GET /api/inventory/health/
```

## Catalog events

The management command `consume_catalog_events` listens on RabbitMQ exchange `catalog.events` for routing key `product.created`. A valid event includes `data.id` and `data.stock`; the consumer creates an inventory record with that initial quantity. Duplicate events do not reset an existing inventory quantity.

Invalid messages are rejected to a dead-letter exchange/queue. Database errors are requeued after a short delay. The worker must be running for new Catalog products to be initialized automatically.

## Configuration

See [`.env.example`](.env.example). The service uses database variables `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, plus `DJANGO_SECRET_KEY` and `JWT_SIGNING_KEY`. RabbitMQ host and port default to `rabbitmq:5672` and can be overridden with `RABBITMQ_HOST` and `RABBITMQ_PORT`.

## Run and test

From the repository root:

```bash
docker compose up -d --build inventory-db inventory-service rabbitmq
docker compose exec inventory-service python manage.py migrate
docker compose logs -f inventory-service inventory-worker
docker compose run --rm inventory-service python manage.py test inventory
```

Use the actual database and worker service names defined in the root `docker-compose.yml`.

## Limitations

- Reservation expiry and automated cleanup are not implemented.
- A reservation can be confirmed by an authenticated caller; internal-service authorization should be strengthened before production.
- Reliable event publication, monitoring, and dead-letter replay tooling remain future improvements.
