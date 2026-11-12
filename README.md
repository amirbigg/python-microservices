# Python Microservices — Educational E-commerce Platform

A learning project for building an e-commerce backend with **Django REST Framework** and a **microservices architecture**. The repository is maintained as a monorepo: application services, API gateway, infrastructure, and observability configuration live together.

> **Project status (November 2026):** The core e-commerce services and monitoring stack are present in the repository. OpenTelemetry packages and instrumented startup commands have also been added to the Django services and workers. End-to-end trace propagation and trace visibility in Grafana Tempo should still be verified. The current startup issue being addressed is Django failing when `DEBUG=False` and `ALLOWED_HOSTS` is empty or is not passed into a container.

## Contents

- [Project goals](#project-goals)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Services](#services)
- [Technology stack](#technology-stack)
- [Request and event flows](#request-and-event-flows)
- [Getting started](#getting-started)
- [Environment configuration](#environment-configuration)
- [Database migrations](#database-migrations)
- [API gateway and service URLs](#api-gateway-and-service-urls)
- [Monitoring, logging, and tracing](#monitoring-logging-and-tracing)
- [Testing](#testing)
- [Operational commands](#operational-commands)
- [Security considerations](#security-considerations)
- [Current limitations and follow-up work](#current-limitations-and-follow-up-work)

## Project goals

This educational project demonstrates practical microservices concepts through an e-commerce backend:

- Service boundaries and independent Django applications.
- Data ownership and service-to-service communication.
- Synchronous HTTP communication and asynchronous event processing.
- JWT-based authentication across services.
- Inventory reservation and compensating actions during checkout.
- Containerized development with Docker Compose.
- Metrics, centralized container logs, alerting, and distributed tracing.

**Payment Service is intentionally out of scope for the current stage.** Checkout currently ends in an `awaiting_payment` state; payment processing is not implemented.

## Architecture

```text
                              Client
                                |
                                v
                         Nginx API Gateway
                           localhost:8080
                                |
          +---------------------+----------------------+
          |            |             |          |      |
          v            v             v          v      v
      User Service  Catalog       Cart      Inventory  Order
          |         Service      Service     Service  Service
          |            |             |          |      |
          v            v             v          v      v
       User DB      Catalog DB     Redis    Inventory  Order DB
                                               DB
                        |
                        | product.created event
                        v
                     RabbitMQ
                        |
                 Inventory Worker

     Metrics: Prometheus + exporters + cAdvisor --> Grafana
     Logs:    Docker --> Grafana Alloy --> Loki --> Grafana
     Traces:  Django services/workers --> OTLP --> Tempo --> Grafana
```

### Architectural principles

- **Service ownership:** Each service owns its application logic and data. A service must not query another service's database directly.
- **Synchronous communication:** HTTP APIs are used when an immediate response is required.
- **Asynchronous communication:** RabbitMQ carries domain events such as `product.created`.
- **Cart storage:** Redis stores cart state; it is not the authoritative inventory database.
- **Checkout coordination:** Order coordinates cart retrieval, product lookup, and stock reservation. This is a distributed workflow, not a single ACID transaction.
- **Observability:** Prometheus collects metrics, Loki stores container logs, and Tempo receives OpenTelemetry traces.

## Repository layout

```text
.
├── docker-compose.yml
├── README.md
├── infrastructure/
│   ├── nginx/nginx.conf
│   ├── rabbitmq/
│   └── monitoring/
│       ├── prometheus/
│       │   ├── prometheus.yml
│       │   └── rules/
│       ├── grafana/provisioning/datasources/
│       ├── alertmanager/alertmanager.yml
│       ├── loki/loki-config.yml
│       ├── alloy/config.alloy
│       └── tempo/tempo.yml
└── services/
    ├── user-service/
    ├── catalog-service/
    ├── cart-service/
    ├── inventory-service/
    └── order-service/
```

Each service contains its own Django project, application code, requirements, and local environment configuration.

## Services

### 1. User Service

**Directory:** `services/user-service`  
**Container port:** `8000`

Responsibilities:
- User registration and authentication.
- JWT access and refresh token issuance.
- Authenticated current-user information.

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/users/register/` | Register a user |
| `POST` | `/api/users/login/` | Obtain JWT tokens |
| `GET` | `/api/users/me/` | Retrieve the authenticated user |
| `GET` | `/api/users/health/` | Health check |

### 2. Catalog Service

**Directory:** `services/catalog-service`  
**Container port:** `8001`

Responsibilities:
- Manage product categories and products.
- Provide product information to other services.
- Use Redis for caching where configured.
- Publish product-created events to RabbitMQ.
- Run a Celery worker for background tasks.

| Method | Route | Purpose |
|---|---|---|
| `GET`, `POST` | `/api/catalog/categories/` | List or create categories |
| `GET`, `POST` | `/api/catalog/products/` | List or create products |
| `GET` | `/api/catalog/health/` | Health check |

Exact methods, permissions, filters, and response schemas are defined by the current serializers, views, and URL/router configuration.

### 3. Cart Service

**Directory:** `services/cart-service`  
**Container port:** `8002`

Responsibilities:
- Store a user's cart in Redis.
- Validate product information through Catalog.
- Check stock availability through Inventory before adding or increasing quantities.
- Provide cart data to Order during checkout.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/cart/` | Retrieve the current user's cart |
| `POST` | `/api/cart/items/` | Add an item |
| `PATCH` | `/api/cart/items/{product_id}/` | Change item quantity |
| `DELETE` | `/api/cart/items/{product_id}/` | Remove an item |
| `DELETE` | `/api/cart/clear/` | Clear the cart |
| `GET` | `/api/cart/health/` | Health check |

Adding an item performs an availability check; it does **not** reserve stock. Inventory may change before checkout, so Order must request an actual reservation.

### 4. Inventory Service

**Directory:** `services/inventory-service`  
**Container port:** `8003`

Responsibilities:
- Own inventory records.
- Check available stock.
- Reserve and release stock for orders.
- Consume Catalog's `product.created` events through `inventory-worker`.
- Initialize inventory records from event data.

The event consumer is intended to handle duplicate product-created events safely. Verify exact Inventory API paths and payload schemas against the current URL and view implementations.

### 5. Order Service

**Directory:** `services/order-service`  
**Container port:** `8004`

Responsibilities:
- Own order and order-item records.
- Retrieve the authenticated user's cart.
- Retrieve product information and prices from Catalog.
- Request stock reservations from Inventory.
- Attempt compensating stock releases when checkout fails.
- Clear the cart after successful reservation.
- Restrict order access to the order owner.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/orders/health/` | Health check |
| `POST` | `/api/orders/checkout/` | Create an order from the current cart |
| `GET` | `/api/orders/` | List the current user's orders |
| `GET` | `/api/orders/{order_id}/` | Retrieve an order |

Checkout requires JWT authentication and an `Idempotency-Key` header. A successful checkout currently produces an order in the `awaiting_payment` state. Payment capture and final reservation confirmation are not implemented.

## Technology stack

**Application:** Python, Django, Django REST Framework, SimpleJWT, drf-spectacular/OpenAPI tooling, HTTPX and other HTTP clients.

**Data and messaging:** PostgreSQL, Redis, RabbitMQ, Celery.

**Containers and gateway:** Docker, Docker Compose, Nginx.

**Observability:** Prometheus, Grafana, cAdvisor, PostgreSQL exporters, Redis Exporter, RabbitMQ Prometheus metrics endpoint, Alertmanager, Grafana Loki, Grafana Alloy, Grafana Tempo, OpenTelemetry instrumentation and OTLP exporter.

## Request and event flows

### Product creation and inventory initialization

1. A product is created through Catalog.
2. Catalog publishes a `product.created` event to RabbitMQ.
3. `inventory-worker` consumes the event.
4. Inventory creates or initializes the corresponding stock record.
5. Duplicate event handling should not create duplicate inventory records.

### Checkout

1. The client sends `POST /api/orders/checkout/` with a valid JWT and an `Idempotency-Key` header.
2. Order retrieves the user's cart from Cart.
3. Order retrieves current product details and prices from Catalog.
4. Order creates the order and item snapshots in its own database.
5. Order asks Inventory to reserve stock for the order items.
6. If a reservation fails, Order attempts compensating releases for reservations already made and marks the order as failed.
7. If all reservations succeed, Order clears the cart and moves the order to `awaiting_payment`.
8. Payment processing is deferred.

This is an educational Saga-style workflow. It is not a distributed transaction. Compensation can fail, and a process crash can leave work requiring reconciliation.

## Getting started

### Prerequisites

- Docker Engine or Docker Desktop.
- Docker Compose v2 (`docker compose`).
- Git.

### 1. Clone the repository

```bash
git clone https://github.com/amirbigg/python-microservices.git
cd python-microservices
```

### 2. Configure environment variables

Create the root `.env` file for Compose-level database and Grafana credentials. Create service environment files expected by `env_file` in `docker-compose.yml`:

```text
services/user-service/.env
services/catalog-service/.env
services/cart-service/.env
services/inventory-service/.env
services/order-service/.env
```

Use the matching `.env.example` files if present. Do not commit real environment files or secrets.

The root Compose configuration expects variables with names such as:

```env
USER_DB_NAME=...
USER_DB_USER=...
USER_DB_PASSWORD=...

CATALOG_DB_NAME=...
CATALOG_DB_USER=...
CATALOG_DB_PASSWORD=...

INVENTORY_DB_NAME=...
INVENTORY_DB_USER=...
INVENTORY_DB_PASSWORD=...

ORDER_DB_NAME=...
ORDER_DB_USER=...
ORDER_DB_PASSWORD=...

GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=change-this-password
```

The actual values must match the checked-out service settings and Compose configuration.

### 3. Start the stack

```bash
docker compose up -d --build
docker compose ps
```

### 4. Check logs

```bash
docker compose logs -f user-service
docker compose logs -f catalog-service
docker compose logs -f cart-service
docker compose logs -f inventory-service
docker compose logs -f order-service
docker compose logs -f catalog-worker
docker compose logs -f inventory-worker
```

## Environment configuration

### Django `DEBUG` and `ALLOWED_HOSTS`

When `DEBUG=False`, Django requires a non-empty `ALLOWED_HOSTS`. Each service's `.env` must provide the hosts accepted by that service, and Compose must pass those variables into the container through `env_file` or `environment`.

A robust settings pattern is:

```python
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "localhost,127.0.0.1"
    ).split(",")
    if host.strip()
]
```

Example development values (adjust to the hosts and domain actually used):

```env
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,user-service,catalog-service,cart-service,inventory-service,order-service
```

Do not use `ALLOWED_HOSTS=*` as a substitute for a deliberate deployment configuration.

After changing environment values, recreate containers:

```bash
docker compose up -d --force-recreate
```

If application dependencies or source code changed, rebuild:

```bash
docker compose build
docker compose up -d
```

### JWT configuration

For the current shared HS256 learning setup, services that validate the same access tokens must use the same signing key. Keep the key secret and out of source control. A production design should consider asymmetric signing and service-specific authorization.

### OpenTelemetry environment

The intended OTLP exporter configuration for a service inside the Compose network is:

```env
OTEL_SERVICE_NAME=user-service
OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=none
OTEL_LOGS_EXPORTER=none
OTEL_PROPAGATORS=tracecontext,baggage
```

Use a distinct `OTEL_SERVICE_NAME` for each process: `user-service`, `catalog-service`, `cart-service`, `inventory-service`, `order-service`, `catalog-worker`, and `inventory-worker`.

`tempo:4317` is the Tempo OTLP gRPC endpoint from inside the Docker network. A process running on the host needs an appropriate host address instead.

## Database migrations

Run migrations for services using Django-managed databases:

```bash
docker compose exec user-service python manage.py migrate
docker compose exec catalog-service python manage.py migrate
docker compose exec inventory-service python manage.py migrate
docker compose exec order-service python manage.py migrate
```

If a service container is not running, use `docker compose run --rm <service> python manage.py migrate` instead of `exec`.

The current Compose configuration does not define a separate Cart PostgreSQL container. Check the Cart service's configured database backend before running migration commands for it.

## API gateway and service URLs

Nginx listens on host port `8080` and routes requests by path prefix.

| Service | Gateway route | Internal service |
|---|---|---|
| User | `/api/users/` | `user-service:8000` |
| Catalog | `/api/catalog/` | `catalog-service:8001` |
| Cart | `/api/cart/` | `cart-service:8002` |
| Inventory | `/api/inventory/` | `inventory-service:8003` |
| Order | `/api/orders/` | `order-service:8004` |

Gateway base URL:

```text
http://localhost:8080
```

Development ports are also published directly: User `8000`, Catalog `8001`, Cart `8002`, Inventory `8003`, and Order `8004`. In production, expose only the intended gateway and infrastructure endpoints.

## Monitoring, logging, and tracing

The observability stack is defined in `docker-compose.yml`.

### Metrics — Prometheus

Prometheus scrapes:
- Prometheus itself.
- cAdvisor for container metrics.
- `/metrics` endpoints on all five Django services.
- PostgreSQL exporters for User, Catalog, Inventory, and Order databases.
- Redis Exporter.
- RabbitMQ's Prometheus metrics endpoint on port `15692`.

Configuration: `infrastructure/monitoring/prometheus/prometheus.yml`

Prometheus UI: `http://localhost:9090`

### Dashboards — Grafana

Grafana UI: `http://localhost:3000`

The admin username and password are configurable through `GRAFANA_ADMIN_USER` and `GRAFANA_ADMIN_PASSWORD` in the root `.env`. Change default credentials before shared or production use.

### Container metrics — cAdvisor

cAdvisor exposes Docker container resource metrics to Prometheus.

### Alerting — Alertmanager

Alertmanager UI: `http://localhost:9093`

Configuration: `infrastructure/monitoring/alertmanager/alertmanager.yml`

The checked-in configuration is a template. Configure a valid notification destination and provide SMTP credentials securely through environment variables or a secret manager before expecting email notifications. Do not commit SMTP passwords.

Prometheus loads rule files from `infrastructure/monitoring/prometheus/rules/`.

### Centralized logs — Loki and Alloy

- Loki receives and stores log streams.
- Grafana Alloy discovers Docker containers and forwards their logs to Loki.
- Alloy uses the Docker socket to discover and collect container logs.

Configuration files:
- `infrastructure/monitoring/loki/loki-config.yml`
- `infrastructure/monitoring/alloy/config.alloy`

Loki is exposed on port `3100`; Alloy's HTTP interface is exposed on port `12345`. Add Loki as a Grafana data source if it is not already provisioned.

### Distributed tracing — OpenTelemetry and Tempo

Tempo receives OTLP traces over:
- gRPC: port `4317`
- HTTP: port `4318`

Tempo query/API port: `3200`

Configuration: `infrastructure/monitoring/tempo/tempo.yml`

The five Django services and the Catalog and Inventory workers use `opentelemetry-instrument` in their Compose startup commands. Their requirements files include Django, HTTP client, PostgreSQL, Redis, Celery, and OTLP instrumentation packages.

To inspect traces:

1. Start the stack and confirm that services and workers are running.
2. Send requests to real API endpoints that exercise application logic and downstream service calls.
3. Open Grafana at `http://localhost:3000`.
4. Open **Explore** and select Tempo as the data source.
5. Search for service names such as `user-service` or `order-service`.
6. Inspect spans and verify whether downstream HTTP calls appear under the same trace.

**Important:** Adding instrumentation packages and changing process commands does not prove that distributed traces are complete. Verify that OTEL environment variables reach each container, requests reach Tempo, and context propagation works across service boundaries. The OpenTelemetry rollout remains pending end-to-end verification until this test succeeds.

## Testing

Run tests separately for each service:

```bash
docker compose run --rm user-service python manage.py test
docker compose run --rm catalog-service python manage.py test
docker compose run --rm cart-service python manage.py test
docker compose run --rm inventory-service python manage.py test inventory
docker compose run --rm order-service python manage.py test orders
```

Some tests require databases or dependent services. Run integration and end-to-end checkout tests where the required services are available.

## Operational commands

```bash
# Start all services
docker compose up -d

# Build images
docker compose build

# Rebuild and start
docker compose up -d --build

# Show running services
docker compose ps

# Follow logs for one service
docker compose logs -f order-service

# Restart a service
docker compose restart order-service

# Recreate containers after environment changes
docker compose up -d --force-recreate

# Stop the stack (preserve named volumes)
docker compose down

# Stop the stack and delete named volumes (destructive)
docker compose down -v
```

## Security considerations

- Never commit `.env` files, Django secret keys, JWT signing keys, database passwords, SMTP credentials, or other secrets.
- Rotate credentials accidentally committed to a public repository.
- Use `DEBUG=False` and explicit `ALLOWED_HOSTS` outside local-only development.
- Use HTTPS at the public gateway in production.
- Change default Grafana credentials.
- Restrict access to Prometheus, Grafana, Alertmanager, Loki, Tempo, RabbitMQ management, and exporter endpoints.
- The current Compose setup is for local learning, not hardened production use.
- Alloy mounts the Docker socket; access to this socket is highly privileged.
- Do not expose database ports or internal service ports publicly in production.
- A shared HS256 signing key is a learning simplification, not a complete production authorization architecture.

## Current limitations and follow-up work

- **Payment Service is intentionally deferred.** No payment processing or payment confirmation is implemented.
- Order checkout ends at `awaiting_payment`.
- Reservation expiry, cancellation, and post-payment confirmation workflows need implementation.
- Checkout recovery after process crashes and robust reconciliation need further work.
- A transactional outbox for reliable event publication is not yet part of the documented architecture.
- Dead-letter replay and automated event recovery need additional tooling.
- Distributed trace propagation and complete multi-service traces must be verified end to end.
- Review the Cart data configuration against the intended architecture: Compose does not define a Cart PostgreSQL database, and the Cart Django settings have previously been observed using SQLite.
- Alertmanager's SMTP notification values must be configured securely before email delivery can work.
- Compose currently uses Django's development `runserver`; production should use an appropriate WSGI/ASGI server.
- Run service test suites and a complete checkout flow after infrastructure or application changes.

---

## License

This repository is an educational project. Add a license file if you intend to define reuse and distribution terms.
