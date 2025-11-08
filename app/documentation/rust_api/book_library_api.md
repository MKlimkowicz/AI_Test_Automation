# Book Library API Documentation

## Overview
A RESTful API for managing a book library built with Rust and Actix-web. This API provides CRUD operations for books with ISBN validation and availability tracking.

## Technology Stack
- **Framework**: Actix-web 4.4
- **Language**: Rust (Edition 2021)
- **Data Storage**: In-memory (Mutex-protected Vec)
- **Serialization**: Serde + Serde JSON

## Base URL
```
http://127.0.0.1:8080
```

## Data Model

### Book
```rust
{
  "id": u32,              // Unique identifier (auto-generated)
  "title": String,        // Book title
  "author": String,       // Book author
  "isbn": String,         // ISBN (must be unique)
  "available": bool       // Availability status
}
```

## API Endpoints

### 1. Health Check
**GET** `/health`

Returns the health status of the API service.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "book-library-api"
}
```

**Purpose**: Used for monitoring and load balancer health checks.

### 2. Get All Books
**GET** `/api/books`

Retrieves all books in the library.

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "title": "The Rust Programming Language",
    "author": "Steve Klabnik",
    "isbn": "978-1718500440",
    "available": true
  },
  {
    "id": 2,
    "title": "Programming Rust",
    "author": "Jim Blandy",
    "isbn": "978-1492052593",
    "available": true
  }
]
```

### 3. Search Books
**GET** `/api/books/search`

Search for books using query parameters.

**Query Parameters:**
- `author` (string, optional) - Filter by author name (case-insensitive partial match)
- `available` (boolean, optional) - Filter by availability status

**Example Request:**
```
GET /api/books/search?author=Klabnik&available=true
```

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "title": "The Rust Programming Language",
    "author": "Steve Klabnik",
    "isbn": "978-1718500440",
    "available": true
  }
]
```

### 4. Get Book by ID
**GET** `/api/books/{id}`

Retrieves a specific book by its ID.

**Path Parameters:**
- `id` (u32, required) - The book's unique identifier

**Response (200 OK):**
```json
{
  "id": 1,
  "title": "The Rust Programming Language",
  "author": "Steve Klabnik",
  "isbn": "978-1718500440",
  "available": true
}
```

**Error Responses:**
- `404 Not Found` - Book does not exist
```json
{
  "error": "Book with id 999 not found"
}
```

### 5. Create Book
**POST** `/api/books`

Creates a new book in the library.

**Request Body:**
```json
{
  "title": "Rust in Action",
  "author": "Tim McNamara",
  "isbn": "978-1617294556"
}
```

**Validation Rules:**
- `title`: Required, cannot be empty or whitespace-only
- `author`: Required, cannot be empty or whitespace-only
- `isbn`: Required, cannot be empty, must be unique

**Response (201 Created):**
```json
{
  "id": 3,
  "title": "Rust in Action",
  "author": "Tim McNamara",
  "isbn": "978-1617294556",
  "available": true
}
```

**Error Responses:**
- `400 Bad Request` - Invalid input data
```json
{
  "error": "Title cannot be empty"
}
```
- `409 Conflict` - ISBN already exists
```json
{
  "error": "Book with this ISBN already exists"
}
```

### 6. Update Book
**PUT** `/api/books/{id}`

Updates an existing book's information. All fields are optional.

**Path Parameters:**
- `id` (u32, required) - The book's unique identifier

**Request Body:**
```json
{
  "title": "Updated Title",
  "author": "Updated Author",
  "isbn": "978-1234567890",
  "available": false
}
```

**Response (200 OK):**
```json
{
  "id": 1,
  "title": "Updated Title",
  "author": "Updated Author",
  "isbn": "978-1234567890",
  "available": false
}
```

**Error Responses:**
- `400 Bad Request` - Invalid input data
- `404 Not Found` - Book does not exist
- `409 Conflict` - ISBN already in use by another book

### 7. Delete Book
**DELETE** `/api/books/{id}`

Permanently removes a book from the library.

**Path Parameters:**
- `id` (u32, required) - The book's unique identifier

**Response (204 No Content)**

**Error Responses:**
- `404 Not Found` - Book does not exist
```json
{
  "error": "Book with id 999 not found"
}
```

## Business Rules

### ISBN Uniqueness
- Each book must have a unique ISBN
- Creating or updating a book with a duplicate ISBN returns 409 Conflict
- ISBN validation occurs before any database operation

### Availability Tracking
- New books are created with `available: true` by default
- Availability can be toggled via PUT request
- Used for tracking if a book is currently checked out

### ID Generation
- IDs are auto-generated sequentially starting from 1
- IDs are never reused, even after deletion
- Thread-safe ID generation using Mutex

## Error Handling

All error responses follow this structure:
```json
{
  "error": "Descriptive error message"
}
```

### HTTP Status Codes
- `200 OK` - Successful GET/PUT request
- `201 Created` - Successful POST request
- `204 No Content` - Successful DELETE request
- `400 Bad Request` - Invalid input data
- `404 Not Found` - Resource not found
- `409 Conflict` - Duplicate ISBN
- `500 Internal Server Error` - Server error

## Concurrency & Thread Safety

The API uses Rust's `Mutex` to ensure thread-safe access to the book collection:
- Multiple concurrent reads are serialized
- Write operations (create, update, delete) acquire exclusive locks
- No race conditions or data corruption possible

## Testing Requirements

### Unit Tests
1. **Book Creation**
   - Valid book creation with all fields
   - Reject empty title
   - Reject empty author
   - Reject empty ISBN
   - Reject duplicate ISBN

2. **Book Retrieval**
   - Get all books returns correct list
   - Get book by valid ID
   - Get book by invalid ID returns 404
   - Search by author (case-insensitive)
   - Search by availability status

3. **Book Updates**
   - Update title only
   - Update author only
   - Update ISBN only
   - Update availability only
   - Update multiple fields
   - Reject empty values
   - Reject duplicate ISBN on update
   - Update non-existent book returns 404

4. **Book Deletion**
   - Delete existing book
   - Delete non-existent book returns 404
   - Verify book is removed from collection

5. **Concurrency Tests**
   - Multiple simultaneous reads
   - Concurrent create operations
   - Race condition testing for ID generation

### Integration Tests
1. Full CRUD workflow
2. Health check endpoint
3. Search functionality with various filters
4. Error response format validation

## Performance Considerations

- In-memory storage provides fast access
- Mutex contention may occur under high concurrent load
- Search operations are O(n) - linear scan through all books
- Consider migrating to a real database for production use

## Future Enhancements

1. Persistent storage (PostgreSQL/SQLite)
2. Authentication and authorization
3. Pagination for book listing
4. Advanced search (by title, ISBN prefix, etc.)
5. Book categories/genres
6. Borrowing history tracking
7. Due date management

