# User Management API Specification

## Overview
A RESTful API for managing user accounts with basic CRUD operations.

## Base URL
```
http://localhost:5000/api/v1
```

## Authentication
All endpoints require Bearer token authentication in the Authorization header:
```
Authorization: Bearer <token>
```

## Endpoints

### 1. Create User
**POST** `/users`

Creates a new user account.

**Request Body:**
```json
{
  "username": "string (required, 3-50 chars)",
  "email": "string (required, valid email)",
  "password": "string (required, min 8 chars)",
  "full_name": "string (optional)"
}
```

**Response (201 Created):**
```json
{
  "id": "integer",
  "username": "string",
  "email": "string",
  "full_name": "string",
  "created_at": "datetime",
  "is_active": true
}
```

**Error Responses:**
- `400 Bad Request` - Invalid input data
- `409 Conflict` - Username or email already exists

### 2. Get User by ID
**GET** `/users/{user_id}`

Retrieves a specific user by their ID.

**Path Parameters:**
- `user_id` (integer, required) - The user's unique identifier

**Response (200 OK):**
```json
{
  "id": "integer",
  "username": "string",
  "email": "string",
  "full_name": "string",
  "created_at": "datetime",
  "last_login": "datetime",
  "is_active": true
}
```

**Error Responses:**
- `404 Not Found` - User does not exist

### 3. List All Users
**GET** `/users`

Retrieves a paginated list of all users.

**Query Parameters:**
- `page` (integer, optional, default: 1) - Page number
- `per_page` (integer, optional, default: 20, max: 100) - Items per page
- `is_active` (boolean, optional) - Filter by active status

**Response (200 OK):**
```json
{
  "users": [
    {
      "id": "integer",
      "username": "string",
      "email": "string",
      "full_name": "string",
      "is_active": true
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "pages": 5
  }
}
```

### 4. Update User
**PUT** `/users/{user_id}`

Updates an existing user's information.

**Path Parameters:**
- `user_id` (integer, required) - The user's unique identifier

**Request Body:**
```json
{
  "email": "string (optional)",
  "full_name": "string (optional)",
  "is_active": "boolean (optional)"
}
```

**Response (200 OK):**
```json
{
  "id": "integer",
  "username": "string",
  "email": "string",
  "full_name": "string",
  "updated_at": "datetime",
  "is_active": true
}
```

**Error Responses:**
- `400 Bad Request` - Invalid input data
- `404 Not Found` - User does not exist
- `409 Conflict` - Email already in use

### 5. Delete User
**DELETE** `/users/{user_id}`

Soft deletes a user account (sets is_active to false).

**Path Parameters:**
- `user_id` (integer, required) - The user's unique identifier

**Response (204 No Content)**

**Error Responses:**
- `404 Not Found` - User does not exist

## Data Validation Rules

### Username
- Required for creation
- 3-50 characters
- Alphanumeric and underscores only
- Must be unique
- Cannot be changed after creation

### Email
- Required for creation
- Valid email format
- Must be unique
- Can be updated

### Password
- Required for creation
- Minimum 8 characters
- Must contain at least one uppercase, one lowercase, and one number
- Stored as bcrypt hash

### Full Name
- Optional
- Maximum 100 characters

## Error Response Format
All error responses follow this structure:
```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

## Rate Limiting
- 100 requests per minute per IP address
- 429 Too Many Requests response when exceeded

## Test Scenarios to Cover

1. **User Creation Tests**
   - Valid user creation with all fields
   - Valid user creation with only required fields
   - Duplicate username rejection
   - Duplicate email rejection
   - Invalid email format rejection
   - Password too short rejection
   - Missing required fields rejection

2. **User Retrieval Tests**
   - Get existing user by ID
   - Get non-existent user (404)
   - List users with default pagination
   - List users with custom pagination
   - Filter users by active status

3. **User Update Tests**
   - Update user email successfully
   - Update user full name
   - Update user active status
   - Attempt to update non-existent user
   - Attempt to update with duplicate email

4. **User Deletion Tests**
   - Soft delete existing user
   - Attempt to delete non-existent user
   - Verify deleted user is marked inactive

5. **Authentication Tests**
   - Request without token (401)
   - Request with invalid token (401)
   - Request with expired token (401)

6. **Validation Tests**
   - Test all validation rules for each field
   - Test boundary conditions (min/max lengths)

7. **Rate Limiting Tests**
   - Verify rate limit enforcement
   - Verify rate limit reset after time window

