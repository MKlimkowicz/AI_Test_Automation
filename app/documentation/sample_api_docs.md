# User Management API Documentation

## Overview
A RESTful API for managing users with authentication capabilities. Built with Flask.

## Base URL
```
http://localhost:5000
```

## Endpoints

### 1. Health Check
**GET** `/health`

Check if the API is running.

**Response (200 OK)**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "service": "User Management API"
}
```

---

### 2. Create User
**POST** `/api/users`

Create a new user account.

**Request Body**:
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "securepass123"
}
```

**Validation Rules**:
- `username`: Required, 3-50 characters, must be unique
- `email`: Required, valid email format, must be unique
- `password`: Required, minimum 8 characters

**Response (201 Created)**:
```json
{
  "id": 3,
  "username": "john_doe",
  "email": "john@example.com",
  "created_at": "2024-01-15T10:30:00"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid input or validation failure
- `409 Conflict`: Username or email already exists

---

### 3. Get User by ID
**GET** `/api/users/<user_id>`

Retrieve a specific user by their ID.

**Path Parameters**:
- `user_id` (integer, required): The user's unique identifier

**Response (200 OK)**:
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "created_at": "2024-01-01T00:00:00"
}
```

**Error Responses**:
- `404 Not Found`: User does not exist

---

### 4. List All Users
**GET** `/api/users`

Retrieve a paginated list of all users.

**Query Parameters**:
- `page` (integer, optional, default: 1): Page number
- `per_page` (integer, optional, default: 10, max: 100): Items per page

**Example Request**:
```
GET /api/users?page=1&per_page=20
```

**Response (200 OK)**:
```json
{
  "users": [
    {
      "id": 1,
      "username": "admin",
      "email": "admin@example.com",
      "created_at": "2024-01-01T00:00:00"
    },
    {
      "id": 2,
      "username": "user1",
      "email": "user1@example.com",
      "created_at": "2024-01-02T00:00:00"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 2,
    "pages": 1
  }
}
```

---

### 5. Update User
**PUT** `/api/users/<user_id>`

Update an existing user's information.

**Path Parameters**:
- `user_id` (integer, required): The user's unique identifier

**Request Body** (all fields optional):
```json
{
  "email": "newemail@example.com",
  "password": "newpassword123"
}
```

**Validation Rules**:
- `email`: Must be valid email format, must be unique
- `password`: Minimum 8 characters

**Response (200 OK)**:
```json
{
  "id": 1,
  "username": "admin",
  "email": "newemail@example.com",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-15T10:30:00"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid input
- `404 Not Found`: User does not exist
- `409 Conflict`: Email already in use

---

### 6. Delete User
**DELETE** `/api/users/<user_id>`

Delete a user account.

**Path Parameters**:
- `user_id` (integer, required): The user's unique identifier

**Response (204 No Content)**

**Error Responses**:
- `404 Not Found`: User does not exist

---

### 7. User Login
**POST** `/api/auth/login`

Authenticate a user and receive an access token.

**Request Body**:
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Expected Behavior**:
- **Valid credentials**: Returns 200 OK with authentication token
- **Invalid credentials**: Returns 401 Unauthorized

**Response (200 OK)** - For valid credentials:
```json
{
  "token": "fake-jwt-token",
  "user_id": 1
}
```

**Response (401 Unauthorized)** - For invalid credentials:
```json
{
  "error": "Invalid credentials"
}
```

**Error Responses**:
- `400 Bad Request`: Missing username or password
- `401 Unauthorized`: Invalid credentials

---

## Authentication

The API uses token-based authentication. After successful login, include the token in subsequent requests:

```
Authorization: Bearer <token>
```

## Error Response Format

All error responses follow this structure:
```json
{
  "error": "Error message description"
}
```

## Test Credentials

The API comes pre-populated with test users:

| Username | Password    | Email              |
|----------|-------------|-------------------|
| admin    | admin123    | admin@example.com |
| user1    | password123 | user1@example.com |

## Data Validation

### Username
- Required for creation
- 3-50 characters
- Must be unique
- Cannot be changed after creation

### Email
- Required for creation
- Valid email format (contains @ and .)
- Must be unique
- Can be updated

### Password
- Required for creation
- Minimum 8 characters
- Stored as SHA-256 hash
- Can be updated

## Test Scenarios

### Functional Tests
1. Health check returns 200 OK
2. Create user with valid data returns 201 Created
3. Create user with duplicate username returns 409 Conflict
4. Create user with invalid email returns 400 Bad Request
5. Create user with short password returns 400 Bad Request
6. Get existing user by ID returns 200 OK
7. Get non-existent user returns 404 Not Found
8. List users with default pagination works
9. List users with custom pagination works
10. Update user email successfully
11. Update user with duplicate email returns 409 Conflict
12. Delete existing user returns 204 No Content
13. Delete non-existent user returns 404 Not Found

### Security Tests
1. **Login with valid credentials returns 200 OK with token**
2. Login with invalid username returns 401 Unauthorized
3. Login with invalid password returns 401 Unauthorized
4. Login without username returns 400 Bad Request
5. Login without password returns 400 Bad Request
6. Passwords are stored as hashes (not plain text)

### Validation Tests
1. Username too short (< 3 chars) rejected
2. Username too long (> 50 chars) rejected
3. Invalid email format rejected
4. Password too short (< 8 chars) rejected
5. Missing required fields rejected

