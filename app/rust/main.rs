use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use serde::{Deserialize, Serialize};
use std::sync::Mutex;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Book {
    id: u32,
    title: String,
    author: String,
    isbn: String,
    available: bool,
}

#[derive(Serialize, Deserialize)]
struct CreateBookRequest {
    title: String,
    author: String,
    isbn: String,
}

#[derive(Serialize, Deserialize)]
struct UpdateBookRequest {
    title: Option<String>,
    author: Option<String>,
    isbn: Option<String>,
    available: Option<bool>,
}

#[derive(Serialize)]
struct ErrorResponse {
    error: String,
}

struct AppState {
    books: Mutex<Vec<Book>>,
    next_id: Mutex<u32>,
}

async fn health_check() -> impl Responder {
    HttpResponse::Ok().json(serde_json::json!({
        "status": "healthy",
        "service": "book-library-api"
    }))
}

async fn get_books(data: web::Data<AppState>) -> impl Responder {
    let books = data.books.lock().unwrap();
    HttpResponse::Ok().json(&*books)
}

async fn get_book_by_id(
    path: web::Path<u32>,
    data: web::Data<AppState>,
) -> impl Responder {
    let book_id = path.into_inner();
    let books = data.books.lock().unwrap();
    
    match books.iter().find(|b| b.id == book_id) {
        Some(book) => HttpResponse::Ok().json(book),
        None => HttpResponse::NotFound().json(ErrorResponse {
            error: format!("Book with id {} not found", book_id),
        }),
    }
}

async fn create_book(
    book_req: web::Json<CreateBookRequest>,
    data: web::Data<AppState>,
) -> impl Responder {
    if book_req.title.trim().is_empty() {
        return HttpResponse::BadRequest().json(ErrorResponse {
            error: "Title cannot be empty".to_string(),
        });
    }
    
    if book_req.author.trim().is_empty() {
        return HttpResponse::BadRequest().json(ErrorResponse {
            error: "Author cannot be empty".to_string(),
        });
    }
    
    if book_req.isbn.trim().is_empty() {
        return HttpResponse::BadRequest().json(ErrorResponse {
            error: "ISBN cannot be empty".to_string(),
        });
    }
    
    let mut books = data.books.lock().unwrap();
    let mut next_id = data.next_id.lock().unwrap();
    
    // Check for duplicate ISBN
    if books.iter().any(|b| b.isbn == book_req.isbn) {
        return HttpResponse::Conflict().json(ErrorResponse {
            error: "Book with this ISBN already exists".to_string(),
        });
    }
    
    let new_book = Book {
        id: *next_id,
        title: book_req.title.clone(),
        author: book_req.author.clone(),
        isbn: book_req.isbn.clone(),
        available: true,
    };
    
    *next_id += 1;
    books.push(new_book.clone());
    
    HttpResponse::Created().json(new_book)
}

async fn update_book(
    path: web::Path<u32>,
    update_req: web::Json<UpdateBookRequest>,
    data: web::Data<AppState>,
) -> impl Responder {
    let book_id = path.into_inner();
    let mut books = data.books.lock().unwrap();
    
    let book_index = match books.iter().position(|b| b.id == book_id) {
        Some(index) => index,
        None => {
            return HttpResponse::NotFound().json(ErrorResponse {
                error: format!("Book with id {} not found", book_id),
            })
        }
    };
    
    let book = &mut books[book_index];
    
    if let Some(title) = &update_req.title {
        if title.trim().is_empty() {
            return HttpResponse::BadRequest().json(ErrorResponse {
                error: "Title cannot be empty".to_string(),
            });
        }
        book.title = title.clone();
    }
    
    if let Some(author) = &update_req.author {
        if author.trim().is_empty() {
            return HttpResponse::BadRequest().json(ErrorResponse {
                error: "Author cannot be empty".to_string(),
            });
        }
        book.author = author.clone();
    }
    
    if let Some(isbn) = &update_req.isbn {
        if isbn.trim().is_empty() {
            return HttpResponse::BadRequest().json(ErrorResponse {
                error: "ISBN cannot be empty".to_string(),
            });
        }
        // Check for duplicate ISBN (excluding current book)
        if books.iter().any(|b| b.isbn == *isbn && b.id != book_id) {
            return HttpResponse::Conflict().json(ErrorResponse {
                error: "Book with this ISBN already exists".to_string(),
            });
        }
        book.isbn = isbn.clone();
    }
    
    if let Some(available) = update_req.available {
        book.available = available;
    }
    
    HttpResponse::Ok().json(book.clone())
}

async fn delete_book(
    path: web::Path<u32>,
    data: web::Data<AppState>,
) -> impl Responder {
    let book_id = path.into_inner();
    let mut books = data.books.lock().unwrap();
    
    let book_index = match books.iter().position(|b| b.id == book_id) {
        Some(index) => index,
        None => {
            return HttpResponse::NotFound().json(ErrorResponse {
                error: format!("Book with id {} not found", book_id),
            })
        }
    };
    
    books.remove(book_index);
    HttpResponse::NoContent().finish()
}

async fn search_books(
    query: web::Query<std::collections::HashMap<String, String>>,
    data: web::Data<AppState>,
) -> impl Responder {
    let books = data.books.lock().unwrap();
    let mut filtered: Vec<Book> = books.clone();
    
    if let Some(author) = query.get("author") {
        let author_lower = author.to_lowercase();
        filtered.retain(|b| b.author.to_lowercase().contains(&author_lower));
    }
    
    if let Some(available) = query.get("available") {
        if let Ok(avail_bool) = available.parse::<bool>() {
            filtered.retain(|b| b.available == avail_bool);
        }
    }
    
    HttpResponse::Ok().json(filtered)
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let app_state = web::Data::new(AppState {
        books: Mutex::new(vec![
            Book {
                id: 1,
                title: "The Rust Programming Language".to_string(),
                author: "Steve Klabnik".to_string(),
                isbn: "978-1718500440".to_string(),
                available: true,
            },
            Book {
                id: 2,
                title: "Programming Rust".to_string(),
                author: "Jim Blandy".to_string(),
                isbn: "978-1492052593".to_string(),
                available: true,
            },
        ]),
        next_id: Mutex::new(3),
    });
    
    println!("Starting Book Library API on http://127.0.0.1:8080");
    
    HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            .route("/health", web::get().to(health_check))
            .route("/api/books", web::get().to(get_books))
            .route("/api/books/search", web::get().to(search_books))
            .route("/api/books/{id}", web::get().to(get_book_by_id))
            .route("/api/books", web::post().to(create_book))
            .route("/api/books/{id}", web::put().to(update_book))
            .route("/api/books/{id}", web::delete().to(delete_book))
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await
}

