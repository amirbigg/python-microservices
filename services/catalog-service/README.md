# Catalog Service

The Catalog Service owns product and category data and exposes API endpoints used by clients and other services.

**Location:** `services/catalog-service/`  
**Framework:** Django + Django REST Framework  
**Database:** PostgreSQL, owned by this service  
**Cache:** Redis is used for the product-list response  
**Gateway prefix:** `/api/catalog/`  
**Internal development port:** `8001`

## Responsibilities

- Create, read, update, and delete categories and products through DRF ModelViewSets.
- Cache the product list and invalidate that cache when products are created, updated, or deleted.
- Publish a `product.created` event to RabbitMQ after a product transaction commits.
- Provide a health endpoint.

Catalog is the source of product names, descriptions, prices, category relationships, and the initial stock value included when a product is created. Inventory is responsible for the authoritative stock quantity after initialization.

## Data model

### Category

| Field | Description |
|---|---|
| `id` | Database-generated primary key |
| `name` | Unique category name, up to 100 characters |
| `slug` | Unique URL-friendly identifier |
| `created`, `updated` | Timestamps |

### Product

| Field | Description |
|---|---|
| `id` | Database-generated primary key |
| `category` | Required reference to a category |
| `name` | Product name, up to 200 characters |
| `description` | Optional text |
| `price` | Integer price |
| `stock` | Non-negative initial stock value; defaults to 0 |
| `is_active` | Whether the product is available for sale; defaults to true |
| `created`, `updated` | Timestamps |

The API uses the model serializer, so request and response fields follow these model fields.

## API

All paths below are relative to `/api/catalog/`.

| Method | Path | Purpose |
|---|---|---|
| GET | `health/` | Health check |
| GET, POST | `categories/` | List categories or create a category |
| GET, PUT, PATCH, DELETE | `categories/{id}/` | Retrieve, update, or delete a category |
| GET, POST | `products/` | List products or create a product |
| GET, PUT, PATCH, DELETE | `products/{id}/` | Retrieve, update, or delete a product |

### Create a category

```http
POST /api/catalog/categories/
Content-Type: application/json
```

```json
{
  "name": "Accessories",
  "slug": "accessories"
}
```

### Create a product

```http
POST /api/catalog/products/
Content-Type: application/json
```

```json
{
  "category": 1,
  "name": "Example Product",
  "description": "A sample item",
  "price": 2500,
  "stock": 20,
  "is_active": true
}
```

### List products

```http
GET /api/catalog/products/
```

The product-list response is cached under the `product-list` cache key. Product create, update, partial update, and delete operations invalidate that key. The current implementation does not set an explicit cache timeout in the view.

### Health check

```http
GET /api/catalog/health/
```

Example response:

```json
{
  "service": "catalog-service",
  "status": "ok"
}
```

## RabbitMQ event

After a product is created and the database transaction commits, Catalog publishes a durable message to the `catalog.events` topic exchange using the routing key `product.created`.

Example event body:

```json
{
  "event": "product.created",
  "data": {
    "id": 12,
    "name": "Example Product",
    "price": "2500",
    "stock": 20
  }
}
```

The Inventory Service consumes this event to create an inventory record for the new product. The event's `stock` value is the initial quantity; subsequent stock changes belong to Inventory.

## Configuration

See [`.env.example`](.env.example). The service uses database environment variables (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`) and `DJANGO_SECRET_KEY`. The project configuration also uses Redis and RabbitMQ; their service addresses are configured in the Django settings and messaging code.

## Run and test

From the repository root:

```bash
docker compose up -d --build catalog-db catalog-service redis rabbitmq
docker compose exec catalog-service python manage.py migrate
docker compose logs -f catalog-service
docker compose run --rm catalog-service python manage.py test
```

Use the service names actually defined in the root `docker-compose.yml`. The complete stack can be started with `docker compose up -d --build`.

## Limitations

- The API currently exposes the methods provided by DRF ModelViewSet; production authorization policies should be explicitly defined and reviewed.
- Event publishing currently opens a RabbitMQ connection for each published event. A transactional outbox and retry/reconciliation mechanism are future reliability improvements.
- Configure `DEBUG=False`, explicit `ALLOWED_HOSTS`, and production secrets before deployment.
