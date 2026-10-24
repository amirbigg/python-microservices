# Order Service

The Order Service coordinates checkout. It owns order records and order-item snapshots, retrieves the user's cart, reads product details from Catalog, and asks Inventory to reserve stock.

**Location:** `services/order-service/`  
**Framework:** Django REST Framework  
**Database:** PostgreSQL, owned by this service  
**Gateway prefix:** `/api/orders/`  
**Internal development port:** `8004`

## Responsibilities

- Create an order from the authenticated user's cart.
- Read current product names and prices from Catalog.
- Save product and price snapshots in order items.
- Reserve stock through Inventory for each order item.
- Attempt compensating reservation releases if checkout fails.
- Clear the cart after all reservations succeed.
- Return only the authenticated user's own orders.
- Prevent duplicate checkout requests using an idempotency key.

Order does not directly access Cart, Catalog, or Inventory databases. It communicates with those services over HTTP.

## Order states

The model defines these states:

| State | Meaning |
|---|---|
| `processing` | Checkout is being processed |
| `awaiting_payment` | Checkout and reservations succeeded; awaiting payment |
| `paid` | Paid state exists in the model; payment integration is not implemented |
| `cancelled` | Cancelled state exists in the model |
| `failed` | Checkout failed |

The current Checkout flow transitions a successful order from `processing` to `awaiting_payment`. Payment confirmation, cancellation APIs, and reservation expiry workflows are not yet implemented.

## Data model

### Order

- `id`: UUID primary key.
- `customer_id`: numeric ID of the user in User Service.
- `idempotency_key`: client-supplied key, unique per customer.
- `status`: order state.
- `total_amount`: sum of unit price multiplied by quantity for all items.
- `failure_reason`: failure/compensation details when applicable.
- `created`, `updated`: timestamps.

### Order item

- `product_id` and `product_name`: Catalog identifiers and name snapshot.
- `unit_price`: price snapshot obtained from Catalog.
- `quantity`: ordered quantity.
- `reservation_id`: UUID used for the corresponding Inventory reservation.
- `subtotal`: computed as `unit_price * quantity`.

## API

All paths below are relative to `/api/orders/`. All endpoints except health require a valid JWT:

```http
Authorization: Bearer <access-token>
```

| Method | Path | Purpose |
|---|---|---|
| GET | `health/` | Health check |
| POST | `checkout/` | Create an order from the current cart |
| GET | `/` | List the current user's orders |
| GET | `{order_id}/` | Retrieve one of the current user's orders |

### Checkout

```http
POST /api/orders/checkout/
Authorization: Bearer <access-token>
Idempotency-Key: checkout-request-001
```

No request body is required. The service reads the cart from Cart Service.

The `Idempotency-Key` header is required and may contain up to 128 characters. Reusing the same key for the same customer returns the existing order rather than creating a duplicate. If an existing order with that key is still `processing`, the service returns `409 Conflict`.

A successful new checkout returns `201 Created` and an order representation such as:

```json
{
  "id": "b6b4e8ef-1cc7-4b91-bd0d-987ac6a0d46e",
  "status": "awaiting_payment",
  "total_amount": 5000,
  "items": [
    {
      "product_id": 12,
      "product_name": "Example Product",
      "unit_price": 2500,
      "quantity": 2,
      "subtotal": 5000,
      "reservation_id": "6b7c2a8e-0d16-4f8a-92a5-5d19c7b5d4ab"
    }
  ],
  "created": "2026-10-24T09:00:00Z",
  "updated": "2026-10-24T09:00:00Z"
}
```

### List and retrieve orders

```http
GET /api/orders/
Authorization: Bearer <access-token>
```

```http
GET /api/orders/b6b4e8ef-1cc7-4b91-bd0d-987ac6a0d46e/
Authorization: Bearer <access-token>
```

The list is scoped to the current user. The detail endpoint returns `404 Not Found` if the order does not exist or belongs to another user.

### Health check

```http
GET /api/orders/health/
```

## Checkout workflow

1. Validate the JWT and required `Idempotency-Key`.
2. Retrieve the current user's cart from Cart Service.
3. Validate the cart structure and quantities.
4. Retrieve each product from Catalog and validate its active status.
5. Create the order and snapshot its item details and prices.
6. Request a stock reservation from Inventory for each item.
7. If a reservation fails, attempt to release the order's reservations and mark the order failed.
8. If reservations succeed, clear the cart and set the order to `awaiting_payment`.

This is a Saga-style compensating workflow, not a distributed ACID transaction. If a downstream service or the process fails during compensation, manual or automated reconciliation may be required.

## Configuration

See [`.env.example`](.env.example). The service uses database variables `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DJANGO_SECRET_KEY`, and `JWT_SIGNING_KEY`. Downstream URLs are configured with `CART_SERVICE_URL`, `CATALOG_SERVICE_URL`, and `INVENTORY_SERVICE_URL`; Docker service names are used by default in the Compose network.

## Run and test

From the repository root:

```bash
docker compose up -d --build order-db order-service cart-service catalog-service inventory-service
docker compose run --rm order-service python manage.py migrate
docker compose run --rm order-service python manage.py test orders
docker compose logs -f order-service
```

Use the database service name defined in the root `docker-compose.yml`. For the complete environment, run `docker compose up -d --build`.

## Limitations

- Payment processing and order confirmation after payment are not implemented.
- Reservation expiry and cancellation/release APIs are not implemented.
- Checkout recovery after a process crash and robust reconciliation are future work.
- Test the full checkout flow across Cart, Catalog, and Inventory before considering it production-ready.
