# Python Microservices — Educational E-commerce Platform

A learning project for an e-commerce backend built with Django REST Framework and a microservices architecture.

> **Scope:** This repository currently documents five services: User, Catalog, Cart, Inventory, and Order. Payment Service is intentionally excluded from the current documentation work.

## Documentation

Each service has its own README with responsibilities, API endpoints, configuration, and testing instructions.

| Service | Documentation | Responsibility |
|---|---|---|
| User | [User Service README](services/user-service/README.md) | Registration, JWT authentication, current-user profile |
| Catalog | [Catalog Service README](services/catalog-service/README.md) | Product and category data; publishes product-created events |
| Cart | [Cart Service README](services/cart-service/README.md) | Per-user cart state in Redis; validates product and stock availability |
| Inventory | [Inventory Service README](services/inventory-service/README.md) | Authoritative stock and stock reservations |
| Order | [Order Service README](services/order-service/README.md) | Checkout coordination, order records, and stock reservation requests |

## Architecture

```text
                         Client
                           |
                           v
                      Nginx API Gateway
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
     User Service     Catalog Service    Cart Service
          |                |                |
          v                v                v
       User DB          Catalog DB         Redis
                           |
                           | RabbitMQ: product.created
                           v
                    Inventory Event Worker
                           |
                           v
                    Inventory Service
                           |
                           v
                      Inventory DB

                       Order Service
                      /      |      \
                     v       v       v
                   Cart    Catalog  Inventory
                           |
                        Order DB
```

### Architecture principles

- **Data ownership:** Each service owns its data. User, Catalog, Inventory, and Order use their own PostgreSQL databases; Cart stores cart state in Redis.
- **No cross-service database access:** Services communicate over HTTP or asynchronous events instead of querying another service's database.
- **Synchronous communication:** Order retrieves the cart and product details and requests inventory reservations over HTTP.
- **Asynchronous communication:** Catalog publishes `product.created` to RabbitMQ; Inventory consumes the event to initialize stock records.
- **Stock authority:** Inventory is authoritative for available stock. A Cart stock check does not reserve inventory.
- **Checkout coordination:** Order creates an order, saves product/price snapshots, reserves inventory, clears the cart on success, and attempts compensating releases when checkout fails.

## Technology Stack

- Python, Django, Django REST Framework
- PostgreSQL
- Redis
- RabbitMQ
- Celery infrastructure in Catalog
- Docker and Docker Compose
- Nginx API Gateway
- SimpleJWT
- HTTPX for internal HTTP calls

## Run locally

Run commands from the repository root.

### 1. Configure environment variables

Copy each service's `.env.example` to a local `.env` where needed, and fill in values appropriate for your environment. Configure the root `.env` for Docker Compose as required by the current `docker-compose.yml`.

Do not commit actual `.env` files, passwords, Django secret keys, or JWT signing keys. The `.env.example` files are templates; variable names and loading behavior should match the service settings and Compose configuration.

### 2. Start the stack

```bash
docker compose up -d --build
docker compose ps
```

### 3. Apply database migrations

```bash
docker compose run --rm user-service python manage.py migrate
docker compose run --rm catalog-service python manage.py migrate
docker compose run --rm inventory-service python manage.py migrate
docker compose run --rm order-service python manage.py migrate
```

Cart uses Redis for its cart data and does not have a cart database model to migrate.

### 4. Check logs

```bash
docker compose logs -f user-service
docker compose logs -f catalog-service
docker compose logs -f cart-service
docker compose logs -f inventory-service
docker compose logs -f inventory-worker
docker compose logs -f order-service
```

### 5. API base URL

When the gateway is mapped to host port `8080`, use:

```text
http://localhost:8080
```

The API Gateway route prefixes are:

| Prefix | Service |
|---|---|
| `/api/users/` | User |
| `/api/catalog/` | Catalog |
| `/api/cart/` | Cart |
| `/api/inventory/` | Inventory |
| `/api/orders/` | Order |

See the service-specific README files for endpoint details.

## Main API flows

### Authentication

1. Register with `POST /api/users/register/`.
2. Obtain JWT tokens with `POST /api/users/login/`.
3. Send the access token in `Authorization: Bearer <access_token>` for authenticated endpoints.

### Product creation and inventory initialization

1. A product is created through Catalog.
2. Catalog publishes a durable `product.created` message to RabbitMQ after the database transaction commits.
3. Inventory consumes the event and creates its inventory record if one does not already exist.
4. Invalid Inventory events are rejected to a dead-letter queue.

### Checkout

1. The client sends `POST /api/orders/checkout/` with a JWT and an `Idempotency-Key` header.
2. Order retrieves the user's cart from Cart.
3. Order retrieves current product details and prices from Catalog.
4. Order creates the order and order-item snapshots.
5. Order requests a stock reservation for each item from Inventory.
6. If a reservation fails, Order attempts compensating releases and marks the order failed.
7. If all reservations succeed, Order clears the cart and moves the order to `awaiting_payment`.

This is an educational Saga-style workflow, not a distributed ACID transaction. Recovery after process crashes, reconciliation of ambiguous outcomes, and full end-to-end behavior must be tested before production use.

## Run tests

```bash
docker compose run --rm user-service python manage.py test
docker compose run --rm catalog-service python manage.py test
docker compose run --rm cart-service python manage.py test
docker compose run --rm inventory-service python manage.py test inventory
docker compose run --rm order-service python manage.py test orders
```

Some tests require the relevant database or service configuration. Review each service README for details.

## Security and production notes

- Keep `.env` files and all credentials out of Git. Rotate secrets that were ever committed to a public repository.
- Set `DEBUG=False`, configure explicit `ALLOWED_HOSTS`, and use HTTPS at the public gateway in production.
- Services validating the same HS256 JWT currently need a consistent `JWT_SIGNING_KEY`; this shared-key arrangement is a learning simplification.
- Do not expose database ports or internal management endpoints publicly.
- Do not treat an availability check in Cart as an inventory reservation.
- Confirm all endpoint contracts, tests, and end-to-end behavior before describing the stack as production-ready.

## Known limitations

- Payment Service is outside the current documentation scope and is not part of the documented checkout flow.
- Order confirmation after payment is not implemented in this stage.
- Reservation expiry/cancellation workflows and robust recovery from interrupted checkout are incomplete.
- A transactional outbox, dead-letter replay tooling, bounded retry policies, metrics, centralized logging, CI/CD, and production deployment hardening remain future work.

## Suggested next steps

1. Verify endpoint contracts and error handling across Cart, Catalog, Inventory, and Order.
2. Run all service tests and migrations.
3. Test checkout end to end, including insufficient stock and downstream-service failures.
4. Improve recovery and reconciliation for interrupted checkout workflows.
5. Add API schema documentation, observability, CI/CD, and deployment hardening.
