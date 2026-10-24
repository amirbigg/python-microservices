# Cart Service

The Cart Service stores each authenticated user's shopping cart in Redis. It references products by ID and does not own product, price, or inventory records.

**Location:** `services/cart-service/`  
**Framework:** Django REST Framework  
**Storage:** Redis  
**Gateway prefix:** `/api/cart/`  
**Internal development port:** `8002`

## Responsibilities

- Store a separate cart for each user in Redis.
- Retrieve, add, update, remove, and clear cart items.
- Validate product existence and active status through Catalog.
- Check the currently available quantity through Inventory before adding an item or increasing its quantity.
- Require authentication for cart operations.

The Redis key format is `cart:user:<user_id>`. A cart has this basic structure:

```json
{
  "items": [
    {
      "product_id": 12,
      "quantity": 2
    }
  ]
}
```

The cart does not store a price snapshot. Order retrieves current product information from Catalog during checkout.

## API

All paths below are relative to `/api/cart/`. Except for the health endpoint, requests require a valid JWT:

```http
Authorization: Bearer <access-token>
```

| Method | Path | Purpose |
|---|---|---|
| GET | `health/` | Health check |
| GET | `/` | Retrieve the current user's cart |
| POST | `items/` | Add an item or increase its quantity |
| PATCH | `items/{product_id}/` | Set an item's quantity |
| DELETE | `items/{product_id}/` | Remove an item |
| DELETE | `clear/` | Clear the current user's cart |

### Retrieve cart

```http
GET /api/cart/
Authorization: Bearer <access-token>
```

An empty cart is returned as `{"items":[]}`.

### Add an item

```http
POST /api/cart/items/
Authorization: Bearer <access-token>
Content-Type: application/json
```

```json
{
  "product_id": 12,
  "quantity": 2
}
```

If `quantity` is omitted, it defaults to 1. If the product is already in the cart, the requested quantity is added to the existing quantity. The service checks that the product exists, is active, and has enough currently available inventory for the resulting total.

### Update quantity

```http
PATCH /api/cart/items/12/
Authorization: Bearer <access-token>
Content-Type: application/json
```

```json
{
  "quantity": 3
}
```

The quantity must be a positive integer. Increasing the quantity triggers an inventory availability check. Reducing the quantity does not need an additional stock check.

### Remove an item / clear cart

```http
DELETE /api/cart/items/12/
Authorization: Bearer <access-token>
```

```http
DELETE /api/cart/clear/
Authorization: Bearer <access-token>
```

Both operations return the resulting cart (the clear operation returns an empty items list).

## Downstream services

Cart makes HTTP requests to:

- Catalog: `GET /api/catalog/products/{product_id}/`
- Inventory: `GET /api/inventory/items/{product_id}/`

The internal base URLs are controlled by `CATALOG_SERVICE_URL` and `INVENTORY_SERVICE_URL`. See [`.env.example`](.env.example). The service also uses `DJANGO_SECRET_KEY` and `JWT_SIGNING_KEY` for its Django/JWT configuration.

## Run and test

From the repository root:

```bash
docker compose up -d --build cart-service redis catalog-service inventory-service
docker compose logs -f cart-service
docker compose run --rm cart-service python manage.py test
```

For a complete environment, use `docker compose up -d --build`.

## Important behavior and limitations

- **A stock check is not a reservation.** Inventory may change after an item is added to the cart. Order must reserve stock during checkout.
- Cart contents are stored in Redis, not in a relational database. Persistence depends on the Redis configuration.
- The service currently stores product IDs and quantities only; it does not store product names or prices.
- Configure production secrets, HTTPS, explicit allowed hosts, and appropriate request authorization before deployment.
