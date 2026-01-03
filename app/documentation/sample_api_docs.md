# Sample API Documentation

## Overview
A comprehensive RESTful API for e-commerce operations including user management, product catalog, orders, and authentication. Built with Flask.

## Base URL
```
http://localhost:5050
```

## Authentication
Token-based authentication using Bearer tokens. Obtain a token via `/api/auth/login` and include it in subsequent requests:
```
Authorization: Bearer <token>
```
Tokens expire after 24 hours.

## Role-Based Access
- **user**: Can manage own profile, view products, create orders
- **admin**: Full access to all resources, can manage users/products/categories

---

## Endpoints

### Health Check

#### GET /health
Check API status.

**Response (200)**:
```json
{"status": "healthy", "timestamp": "2024-01-15T10:30:00", "service": "Sample API", "version": "2.0.0"}
```

---

### Authentication

#### POST /api/auth/login
Authenticate and receive access token.

**Request**:
```json
{"username": "admin", "password": "admin123"}
```

**Response (200)**:
```json
{"token": "uuid-token", "user_id": 1, "role": "admin", "expires_in": 86400}
```

**Errors**: 400 (missing fields), 401 (invalid credentials), 403 (account deactivated), 429 (rate limited)

**Rate Limit**: 10 attempts per minute per IP

#### POST /api/auth/logout
Invalidate current token. Requires authentication.

**Response (200)**:
```json
{"message": "Logged out successfully"}
```

#### GET /api/auth/me
Get current authenticated user info. Requires authentication.

**Response (200)**:
```json
{"id": 1, "username": "admin", "email": "admin@example.com", "role": "admin", "active": true}
```

---

### Users

#### POST /api/users
Create a new user.

**Request**:
```json
{"username": "john_doe", "email": "john@example.com", "password": "SecurePass1"}
```

**Validation**:
- username: 3-50 chars, alphanumeric + underscore only, unique
- email: valid format, unique
- password: min 8 chars, must contain uppercase, lowercase, and number

**Response (201)**:
```json
{"id": 3, "username": "john_doe", "email": "john@example.com", "role": "user", "created_at": "2024-01-15T10:30:00", "active": true}
```

**Errors**: 400 (validation), 409 (duplicate)

#### GET /api/users/{user_id}
Get user by ID.

**Response (200)**: User object without password
**Errors**: 404 (not found)

#### GET /api/users
List users with pagination and filtering.

**Query Parameters**:
- page (int, default: 1)
- per_page (int, default: 10, max: 100)
- role (string): Filter by role
- active (boolean): Filter by active status

**Response (200)**:
```json
{
  "users": [...],
  "pagination": {"page": 1, "per_page": 10, "total": 2, "pages": 1}
}
```

#### PUT /api/users/{user_id}
Update user.

**Request** (all optional):
```json
{"email": "new@example.com", "password": "NewPass123", "active": false}
```

**Response (200)**: Updated user object
**Errors**: 400, 404, 409

#### DELETE /api/users/{user_id}
Delete user.

**Response**: 204 No Content
**Errors**: 404

#### POST /api/users/bulk
Bulk create users. Requires admin.

**Request**:
```json
{
  "users": [
    {"username": "user1", "email": "user1@example.com", "password": "Pass1234"},
    {"username": "user2", "email": "user2@example.com", "password": "Pass1234"}
  ]
}
```

**Limits**: Max 50 users per request

**Response (201)**:
```json
{"created": [...], "created_count": 2, "errors": [], "error_count": 0}
```

---

### Categories

#### GET /api/categories
List all categories.

**Response (200)**:
```json
{"categories": [{"id": 1, "name": "Electronics", "description": "..."}]}
```

#### GET /api/categories/{category_id}
Get category by ID.

**Response (200)**: Category object
**Errors**: 404

#### POST /api/categories
Create category. Requires admin.

**Request**:
```json
{"name": "Sports", "description": "Sports equipment"}
```

**Validation**: name 2-100 chars, unique

**Response (201)**: Created category
**Errors**: 400, 409

#### DELETE /api/categories/{category_id}
Delete category. Requires admin.

**Response**: 204 No Content
**Errors**: 400 (has products), 404

---

### Products

#### GET /api/products
List products with filtering and sorting.

**Query Parameters**:
- page, per_page (pagination)
- category_id (int): Filter by category
- min_price, max_price (float): Price range
- in_stock (boolean): Filter by stock availability
- sort_by (string): id, name, price, stock
- sort_order (string): asc, desc

**Response (200)**:
```json
{
  "products": [{"id": 1, "name": "Laptop", "price": 999.99, "stock": 50, ...}],
  "pagination": {...}
}
```

#### GET /api/products/{product_id}
Get product with category info.

**Response (200)**:
```json
{"id": 1, "name": "Laptop", "price": 999.99, "category": {"id": 1, "name": "Electronics"}, ...}
```

#### POST /api/products
Create product. Requires admin.

**Request**:
```json
{"name": "Headphones", "price": 79.99, "category_id": 1, "stock": 100, "description": "Wireless headphones"}
```

**Validation**:
- name: 2-200 chars
- price: non-negative number
- category_id: must exist
- stock: non-negative integer

**Response (201)**: Created product

#### PUT /api/products/{product_id}
Update product. Requires admin.

**Request** (all optional):
```json
{"name": "...", "description": "...", "price": 89.99, "stock": 50, "category_id": 2, "active": true}
```

#### DELETE /api/products/{product_id}
Delete product. Requires admin.

**Response**: 204 No Content

#### PUT /api/products/{product_id}/stock
Update product stock. Requires admin.

**Request** (one of):
```json
{"stock": 100}
```
or
```json
{"adjustment": -5}
```

**Response (200)**:
```json
{"id": 1, "name": "Laptop", "stock": 95}
```

---

### Orders

#### POST /api/orders
Create order. Requires authentication.

**Request**:
```json
{
  "items": [
    {"product_id": 1, "quantity": 2},
    {"product_id": 2, "quantity": 1}
  ],
  "shipping_address": "123 Main St"
}
```

**Validation**:
- Product must exist and be active
- Sufficient stock required
- Quantity must be positive integer

**Response (201)**:
```json
{
  "id": 1,
  "user_id": 2,
  "items": [{"product_id": 1, "product_name": "Laptop", "quantity": 2, "unit_price": 999.99, "total": 1999.98}],
  "total": 2049.97,
  "status": "pending",
  "created_at": "..."
}
```

**Side Effect**: Reduces product stock

#### GET /api/orders
List orders. Requires authentication.
- Regular users see only their orders
- Admins see all orders

**Query Parameters**:
- page, per_page
- status: Filter by order status

#### GET /api/orders/{order_id}
Get order details. Requires authentication.
- Users can only view their own orders
- Admins can view any order

**Errors**: 403 (access denied), 404

#### PUT /api/orders/{order_id}/status
Update order status. Requires admin.

**Request**:
```json
{"status": "shipped"}
```

**Valid Statuses**: pending, processing, shipped, delivered, cancelled

**Rules**:
- Cannot update cancelled orders
- Can only cancel pending/processing orders
- Cancellation restores product stock

---

### Search

#### GET /api/search
Search across users, products, categories.

**Query Parameters**:
- q (required): Search query, min 2 chars
- type: all, users, products, categories

**Response (200)**:
```json
{
  "query": "laptop",
  "results": {
    "users": [],
    "products": [{"id": 1, "name": "Laptop", ...}],
    "categories": []
  },
  "total": 1
}
```

---

### Statistics

#### GET /api/stats
Get dashboard statistics. Requires admin.

**Response (200)**:
```json
{
  "users": {"total": 10, "active": 8},
  "products": {"total": 50, "active": 45},
  "orders": {"total": 100, "by_status": {"pending": 5, "delivered": 90, "cancelled": 5}},
  "revenue": {"total": 25000.00},
  "low_stock_products": [{"id": 1, "name": "Laptop", "stock": 5}],
  "categories_count": 3
}
```

---

## Error Response Format
```json
{"error": "Error message description"}
```

## HTTP Status Codes
- 200: Success
- 201: Created
- 204: No Content (successful deletion)
- 400: Bad Request (validation error)
- 401: Unauthorized (missing/invalid token)
- 403: Forbidden (insufficient permissions)
- 404: Not Found
- 409: Conflict (duplicate resource)
- 429: Too Many Requests (rate limited)
- 500: Internal Server Error

---

## Test Data

### Users
| Username | Password | Email | Role |
|----------|----------|-------|------|
| admin | admin123 | admin@example.com | admin |
| user1 | password123 | user1@example.com | user |

### Categories
| ID | Name |
|----|------|
| 1 | Electronics |
| 2 | Books |
| 3 | Clothing |

### Products
| ID | Name | Price | Stock | Category |
|----|------|-------|-------|----------|
| 1 | Laptop | 999.99 | 50 | Electronics |
| 2 | Python Book | 49.99 | 100 | Books |
| 3 | T-Shirt | 19.99 | 200 | Clothing |

