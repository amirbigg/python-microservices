# E-Commerce Microservices

An educational e-commerce platform built with Python, Django, Django REST Framework, and a microservices architecture.

> **Project status:** Under development. This repository is intended for learning and is not production-ready.

## Architecture

The application is organized as independently developed services. Each service owns its data; one service must not directly access another service's database or internal models.

| Service | Responsibility | Storage | Status |
|---|---|---|---|
| User Service | Registration, login, and user identity | PostgreSQL | Implemented |
| Catalog Service | Product and category management | PostgreSQL, Redis cache | Implemented |
| Cart Service | Shopping cart operations | Redis | Implemented; JWT integration/tests need final verification |
| Inventory Service | Product stock tracking and reservations | Dedicated PostgreSQL database | In progress |
| Order Service | Order creation and lifecycle | To be designed | Planned |
| Payment Service | Payment provider integration | To be designed | Planned |
| Notification Service | Order-related notifications | To be designed | Planned |

## Technology Stack

- Python and Django
- Django REST Framework
- PostgreSQL
- Redis
- RabbitMQ
- Celery
- Nginx API Gateway
- Docker and Docker Compose
- JSON Web Tokens (JWT)

Planned additions include OpenAPI/Swagger documentation, broader automated testing, Ruff, GitHub Actions CI/CD, monitoring, and centralized logging.

## Repository Structure

```text
python-microservices/
├── infrastructure/
│   ├── nginx/
│   │   └── nginx.conf
│   └── rabbitmq/
│       └── rabbitmq.conf
├── services/
│   ├── user-service/
│   ├── catalog-service/
│   ├── cart-service/
│   └── inventory-service/   # being developed
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
└── README.md
```

The `inventory-service/` directory and its related Compose/Nginx configuration should be present after completing the current Inventory setup steps. Until those changes are committed, treat the Inventory service as in progress rather than deployed.

## API Gateway

The Nginx API Gateway is intended to be available at `http://localhost:8080`.

| Route prefix | Service |
|---|---|
| `/api/users/` | User Service |
| `/api/catalog/` | Catalog Service |
| `/api/cart/` | Cart Service |
| `/api/inventory/` | Inventory Service (once its gateway route is configured) |

Individual service ports may also be exposed by Docker Compose for local development and debugging.

## Current Progress

### User Service

- [x] Django project and Django REST Framework
- [x] PostgreSQL integration
- [x] Custom User model
- [x] Registration API
- [x] Login API and JWT tokens
- [x] Protected user profile endpoint
- [x] Environment-based configuration
- [x] Basic API tests
- [x] Docker and Docker Compose integration

Endpoints:

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/users/register/` | Register a user |
| POST | `/api/users/login/` | Obtain JWT tokens |
| GET | `/api/users/me/` | Get the authenticated user's profile |
| GET | `/api/users/health/` | Health check |

### Catalog Service

- [x] Django project and Django REST Framework
- [x] Category and Product models
- [x] Dedicated PostgreSQL database
- [x] Category and Product APIs
- [x] Redis caching for the product list
- [x] Product-list cache invalidation
- [x] RabbitMQ event-publishing foundation
- [x] Celery configuration and worker
- [x] Basic API tests
- [x] Docker and Docker Compose integration

Endpoints:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/catalog/health/` | Health check |
| GET, POST | `/api/catalog/categories/` | List or create categories |
| GET, PUT, PATCH, DELETE | `/api/catalog/categories/{id}/` | Retrieve or modify a category |
| GET, POST | `/api/catalog/products/` | List or create products |
| GET, PUT, PATCH, DELETE | `/api/catalog/products/{id}/` | Retrieve or modify a product |

### Cart Service

- [x] Django project and Django REST Framework
- [x] Redis-based cart storage
- [x] Retrieve the cart, add items, update quantities, remove items, and clear the cart
- [x] Catalog Service integration for product validation
- [x] Reject missing and inactive products
- [x] Quantity validation
- [x] Basic API tests
- [x] Stateless JWT authentication configuration added
- [ ] Complete JWT integration and update tests to use authenticated requests
- [ ] Verify JWT authentication end to end using a token from User Service
- [ ] Validate/reserve product stock through Inventory Service

Endpoints:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/cart/health/` | Health check |
| GET | `/api/cart/` | Retrieve the current user's cart |
| POST | `/api/cart/items/` | Add a product to the cart |
| PATCH | `/api/cart/items/{product_id}/` | Update a product quantity |
| DELETE | `/api/cart/items/{product_id}/` | Remove a product |
| DELETE | `/api/cart/clear/` | Clear the cart |

All Cart endpoints other than the health check are intended to require JWT authentication. The authenticated user's ID, not an ID supplied by a request header, identifies the cart owner.

### Inventory Service — In Progress

The initial Inventory Service design uses its own Django project and PostgreSQL database. It stores the Catalog product ID as a scalar field rather than using a cross-service foreign key.

Planned initial API:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/inventory/health/` | Health check |
| GET | `/api/inventory/items/` | List inventory records (JWT required) |
| GET | `/api/inventory/items/{product_id}/` | Retrieve a product's inventory (JWT required) |

Initial implementation checklist:

- [ ] Create the Django project and `inventory` application
- [ ] Add Inventory-specific PostgreSQL configuration and environment variables
- [ ] Add the `InventoryItem` model (`product_id`, `quantity`, timestamps)
- [ ] Add a read-only inventory API
- [ ] Configure stateless JWT authentication
- [ ] Register the model in Django Admin
- [ ] Add the Inventory service and database to Docker Compose
- [ ] Add the `/api/inventory/` route to Nginx
- [ ] Add and pass basic API tests
- [ ] Verify the health endpoint through the API Gateway

Stock reservation/release, atomic concurrency-safe updates, catalog-event handling, and Cart integration are later steps and are not considered implemented yet.

## Infrastructure

Current infrastructure includes or is configured for:

- Docker Compose
- User PostgreSQL database
- Catalog PostgreSQL database
- Redis
- RabbitMQ
- Nginx API Gateway
- Celery worker for Catalog

The Inventory database and service must be added to Compose as part of the current stage.

## Running Locally

### Prerequisites

- Docker
- Docker Compose

### 1. Configure environment files

Copy the root environment template and fill in the required values:

```bash
cp .env.example .env
```

Create each service's local `.env` from its `.env.example` where available. The Inventory Service also needs its own environment file during the current setup stage.

Keep actual `.env` files and secret values out of Git. Use strong, unique Django secret keys. With the current HS256 JWT setup, User Service and downstream services validating its tokens must use the same `JWT_SIGNING_KEY`.

### 2. Build and start the configured services

```bash
docker compose up --build -d
```

### 3. Check containers and logs

```bash
docker compose ps
docker compose logs -f user-service
```

Replace `user-service` with the service name you want to inspect.

### 4. Stop services

```bash
docker compose down
```

Named volumes are preserved by this command unless explicitly removed.

> The start commands above apply only to services already configured in your local Compose file. Complete and test the Inventory Compose configuration before expecting Inventory endpoints to respond.

## Architecture Principles

- Each service owns its data and database.
- Services must not directly query another service's database or internal models.
- HTTP APIs are used for synchronous service-to-service communication.
- RabbitMQ provides asynchronous messaging.
- Celery handles background tasks.
- Redis is used for caching and Cart storage.
- JWT is used for authentication across service boundaries.
- Nginx routes API requests to their target service.
- Environment variables are used for local configuration and secrets.

## Next Steps

1. Complete the initial Inventory Service setup and pass its tests.
2. Finish and verify Cart Service JWT integration and authentication tests.
3. Implement atomic stock reservation and release in Inventory Service.
4. Integrate Catalog product events with Inventory Service and plan how existing stock data will be migrated.
5. Integrate Cart Service with Inventory Service.
6. Create Order Service.
7. Develop Payment Service.
8. Develop Notification Service.
9. Add API documentation, expand automated tests, and introduce code-quality checks.
10. Add CI/CD, monitoring, and centralized logging.

## Learning Goals

This project is intended to build practical experience with microservices architecture, Django REST Framework, authentication between services, database-per-service design, service-to-service communication, caching, asynchronous messaging, Docker, automated testing, CI/CD, and observability.
