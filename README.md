# Python Microservices — Educational E-commerce Platform

A learning project for building an e-commerce backend with Django REST Framework and a microservices architecture.

> **Project status:** This README describes the intended state through the Order Service stage. Verify endpoint contracts, tests, and end-to-end behavior against the current GitHub branch before treating every item as verified or production-ready.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Services](#services)
- [Technology Stack](#technology-stack)
- [Local Development](#local-development)
- [Environment Configuration](#environment-configuration)
- [API Gateway](#api-gateway)
- [Checkout Flow](#checkout-flow)
- [Testing](#testing)
- [Security Notes](#security-notes)
- [Known Limitations](#known-limitations)
- [Next Steps](#next-steps)

## Overview

The goal is to learn microservices concepts by building an e-commerce platform incrementally. Each service owns its own data and communicates with other services through APIs or asynchronous events rather than directly accessing another service's database.

The repository uses a monorepo structure: services live under `services/`, while shared infrastructure configuration lives at the repository root and under `infrastructure/`.

## Architecture

```text
                         Client
                           |
                           v
                      API Gateway
                         Nginx
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
                    Inventory Worker
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
                      \      |      /
                       \     |     /
                         Order DB
```

### Architecture principles

- **Database per service:** User, Catalog, Inventory, and Order each have their own database. Cart uses Redis for cart data.
- **No shared database models:** A service must not query or modify another service's database directly.
- **Synchronous communication:** HTTP APIs are used for request/response interactions such as cart retrieval, product lookup, and stock reservation.
- **Asynchronous communication:** RabbitMQ carries domain events such as `product.created`.
- **Cache and cart state:** Redis stores cart data; it is not the authoritative inventory store.
- **Checkout coordination:** Order coordinates checkout and stock reservation. Payment is not implemented yet.

## Services

### 1. User Service

**Location:** `services/user-service`

Responsibilities:
- User registration and authentication.
- JWT access and refresh tokens.
- Authenticated current-user endpoint.

Endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/users/register/` | Register a user |
| POST | `/api/users/login/` | Obtain JWT tokens |
| GET | `/api/users/me/` | Current authenticated user |
| GET | `/api/users/health/` | Health check |

### 2. Catalog Service

**Location:** `services/catalog-service`

Responsibilities:
- Manage categories and products.
- Expose product details to other services.
- Cache product-list responses in Redis.
- Publish product-created events to RabbitMQ.

Endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| GET/POST | `/api/catalog/categories/` | List or create categories |
| GET/POST | `/api/catalog/products/` | List or create products |
| GET | `/api/catalog/health/` | Health check |

The exact supported methods and permissions depend on the current viewsets and router configuration.

### 3. Cart Service

**Location:** `services/cart-service`

Responsibilities:
- Store each user's cart in Redis.
- Validate products through Catalog.
- Check available inventory through the Inventory API before adding/increasing quantities.
- Keep cart data separate from product and inventory databases.

Endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/cart/` | Retrieve current user's cart |
| POST | `/api/cart/items/` | Add an item |
| PATCH | `/api/cart/items/{product_id}/` | Change item quantity |
| DELETE | `/api/cart/items/{product_id}/` | Remove an item |
| DELETE | `/api/cart/clear/` | Clear the cart |
| GET | `/api/cart/health/` | Health check |

Adding an item checks current availability but **does not reserve stock**. Inventory can change after the check, so checkout must reserve stock atomically.

### 4. Inventory Service

**Location:** `services/inventory-service`

Responsibilities:
- Own inventory records and stock-reservation data.
- Consume `product.created` events from Catalog through a separate RabbitMQ worker.
- Initialize inventory records from the initial stock value in the event.
- Provide APIs for inventory queries and reservation/release operations.

The Catalog event consumer is designed to process duplicate `product.created` events idempotently. Invalid events are routed to a dead-letter queue. A transactional outbox, bounded retries, automated recovery, and monitoring remain future improvements.

> Verify exact Inventory endpoint paths and request/response schemas in `services/inventory-service/inventory/urls.py` and `views.py`; Order's HTTP client must match those definitions.

### 5. Order Service

**Location:** `services/order-service`

Responsibilities:
- Own order and order-item records in a dedicated PostgreSQL database.
- Read the authenticated user's cart.
- Fetch product names and prices from Catalog and save a snapshot in each order.
- Request stock reservations from Inventory.
- Attempt compensating releases if checkout fails.
- Clear the cart after all reservations succeed.
- Return orders only to their owner.

Planned endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/orders/health/` | Health check |
| POST | `/api/orders/checkout/` | Create an order from the current cart |
| GET | `/api/orders/` | List current user's orders |
| GET | `/api/orders/{order_id}/` | Retrieve an order |

Checkout requires a valid JWT and an `Idempotency-Key` header. A successful initial checkout moves the order to `awaiting_payment`; payment processing and final reservation confirmation are not implemented yet.

## Technology Stack

- Python
- Django
- Django REST Framework
- PostgreSQL (separate database per applicable service)
- Redis
- RabbitMQ
- Celery (background-task infrastructure in Catalog)
- Docker and Docker Compose
- Nginx API Gateway
- SimpleJWT
- HTTPX for service-to-service HTTP calls

## Local Development

Commands below assume Docker Compose is configured at the repository root and service names match `docker-compose.yml`.

### Start services

```bash
docker compose up -d --build
docker compose ps
```

### Run migrations

```bash
docker compose exec user-service python manage.py migrate
docker compose exec catalog-service python manage.py migrate
docker compose exec inventory-service python manage.py migrate
docker compose run --rm order-service python manage.py migrate
```

If a service is not running, use `docker compose run --rm <service> python manage.py migrate` instead of `exec`.

### View logs

```bash
docker compose logs -f user-service
docker compose logs -f catalog-service
docker compose logs -f inventory-service
docker compose logs -f inventory-worker
docker compose logs -f order-service
```

### Local endpoint

If the gateway is mapped to port `8080`, the API base URL is:

```text
http://localhost:8080
```

Some services may also expose their own development ports for debugging, depending on the current Compose configuration.

## Environment Configuration

Keep secrets out of Git. Create local `.env` files from the relevant `.env.example` files and fill in real values.

Expected configuration includes:
- Root `.env`: database names, users, and passwords consumed by Docker Compose.
- Service `.env` files: Django secret keys, JWT signing key, database connection settings, and downstream service URLs.

For the current HS256 learning setup, services that validate the same user access tokens must use the same `JWT_SIGNING_KEY`. Never commit real `.env` files or expose signing keys.

Environment variable names must match the current settings files. A `.env.example` is documentation only; it does not automatically configure a service unless the application or Compose loads it.

## API Gateway

Nginx routes requests to the relevant internal service. Expected route prefixes are:

- `/api/users/` → User Service
- `/api/catalog/` → Catalog Service
- `/api/cart/` → Cart Service
- `/api/orders/` → Order Service

Inventory may also be exposed through the gateway if configured in `infrastructure/nginx/nginx.conf`. Internal service-to-service calls use Docker DNS service names and internal ports.

## Checkout Flow

1. The client sends `POST /api/orders/checkout/` with a JWT and `Idempotency-Key`.
2. Order retrieves the user's cart from Cart.
3. Order fetches current product information and price from Catalog.
4. Order creates a local order and order-item snapshots.
5. Order asks Inventory to reserve stock for each item using a unique reservation ID.
6. If a reservation fails, Order attempts to release reservations associated with that order and marks the order failed.
7. If all reservations succeed, Order clears the cart and moves the order to `awaiting_payment`.
8. Payment is handled in a later project stage.

This is an educational Saga-style workflow, not a distributed ACID transaction. Failures during compensation or process termination can leave reservations requiring reconciliation. Checkout retry/recovery and robust handling of ambiguous network outcomes must be tested and improved before production use.

## Testing

Run tests for each service, adapting service names to the current Compose configuration:

```bash
docker compose run --rm user-service python manage.py test
docker compose run --rm catalog-service python manage.py test
docker compose run --rm cart-service python manage.py test
docker compose run --rm inventory-service python manage.py test inventory
docker compose run --rm order-service python manage.py test orders
```

Some tests may require PostgreSQL or additional service configuration. Cross-service end-to-end tests should be run separately from unit tests that mock HTTP clients.

## Security Notes

- Do not commit `.env` files, Django secret keys, JWT signing keys, or real database credentials.
- Rotate any credentials that were previously committed to a public repository.
- Set `DEBUG=False` and configure explicit `ALLOWED_HOSTS` for deployments.
- Use HTTPS at the external gateway in production.
- The current shared HS256 JWT key is a learning simplification; consider asymmetric signing and service-specific authorization for a stronger production design.
- Do not treat a cart stock check as a reservation.
- Do not expose internal database ports or management interfaces publicly in production.

## Known Limitations

- Payment Service is not implemented.
- Order confirmation after payment is not implemented.
- Reservation expiry and cancellation/release workflows are not complete.
- Checkout recovery after process crashes is not complete.
- A transactional outbox for reliable event publication is not implemented.
- Dead-letter replay, bounded retries, and reconciliation tooling remain future work.
- API schemas, CI/CD, metrics, centralized logging, and production deployment hardening remain future work.
- The endpoint contracts in Order's HTTP clients must be verified against the current Inventory and Cart implementations.
- This README describes the intended state through the Order Service stage; run tests and an end-to-end checkout before marking the flow verified.

## Next Steps

1. Verify Inventory API paths and request/response schemas against its implementation.
2. Run Order Service tests and migrations.
3. Verify checkout end to end across Cart, Catalog, and Inventory.
4. Implement Payment Service.
5. Confirm inventory reservations after successful payment.
6. Release reservations when orders are cancelled or expire.
7. Add recovery for interrupted checkout workflows.
8. Improve event delivery reliability with a transactional outbox.
9. Add API documentation, CI/CD, monitoring, and centralized logging.
