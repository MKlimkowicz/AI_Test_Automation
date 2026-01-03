from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import uuid
import re

users = {
    1: {"id": 1, "username": "admin", "email": "admin@example.com", "password": hashlib.sha256("admin123".encode()).hexdigest(), "role": "admin", "created_at": "2024-01-01T00:00:00", "active": True},
    2: {"id": 2, "username": "user1", "email": "user1@example.com", "password": hashlib.sha256("password123".encode()).hexdigest(), "role": "user", "created_at": "2024-01-02T00:00:00", "active": True}
}
next_user_id = 3

categories = {
    1: {"id": 1, "name": "Electronics", "description": "Electronic devices and gadgets"},
    2: {"id": 2, "name": "Books", "description": "Books and publications"},
    3: {"id": 3, "name": "Clothing", "description": "Apparel and accessories"}
}
next_category_id = 4

products = {
    1: {"id": 1, "name": "Laptop", "description": "High-performance laptop", "price": 999.99, "stock": 50, "category_id": 1, "created_at": "2024-01-01T00:00:00", "active": True},
    2: {"id": 2, "name": "Python Book", "description": "Learn Python programming", "price": 49.99, "stock": 100, "category_id": 2, "created_at": "2024-01-02T00:00:00", "active": True},
    3: {"id": 3, "name": "T-Shirt", "description": "Cotton t-shirt", "price": 19.99, "stock": 200, "category_id": 3, "created_at": "2024-01-03T00:00:00", "active": True}
}
next_product_id = 4

orders = {}
next_order_id = 1

tokens = {}

request_counts = {}

def create_app():
    app = Flask(__name__)
    app.config['TESTING'] = False

    def get_current_user(token):
        if not token or token not in tokens:
            return None
        token_data = tokens[token]
        if datetime.fromisoformat(token_data['expires_at']) < datetime.now():
            del tokens[token]
            return None
        return users.get(token_data['user_id'])

    def require_auth(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return jsonify({"error": "Missing or invalid authorization header"}), 401
            token = auth_header[7:]
            user = get_current_user(token)
            if not user:
                return jsonify({"error": "Invalid or expired token"}), 401
            request.current_user = user
            return f(*args, **kwargs)
        return decorated

    def require_admin(f):
        @wraps(f)
        @require_auth
        def decorated(*args, **kwargs):
            if request.current_user.get('role') != 'admin':
                return jsonify({"error": "Admin access required"}), 403
            return f(*args, **kwargs)
        return decorated

    def check_rate_limit(identifier, limit=100, window=60):
        now = datetime.now()
        key = f"{identifier}_{now.strftime('%Y%m%d%H%M')}"
        request_counts[key] = request_counts.get(key, 0) + 1
        if request_counts[key] > limit:
            return False
        return True

    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "Sample API",
            "version": "2.0.0"
        }), 200

    @app.route('/api/users', methods=['POST'])
    def create_user():
        data = request.get_json()
        if not data or 'username' not in data or 'email' not in data or 'password' not in data:
            return jsonify({"error": "Missing required fields: username, email, password"}), 400
        username = data['username'].strip()
        email = data['email'].strip().lower()
        password = data['password']
        if len(username) < 3 or len(username) > 50:
            return jsonify({"error": "Username must be between 3 and 50 characters"}), 400
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            return jsonify({"error": "Username can only contain letters, numbers, and underscores"}), 400
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return jsonify({"error": "Invalid email format"}), 400
        if len(password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400
        if not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password) or not re.search(r'[0-9]', password):
            return jsonify({"error": "Password must contain uppercase, lowercase, and number"}), 400
        for user in users.values():
            if user['username'].lower() == username.lower():
                return jsonify({"error": "Username already exists"}), 409
            if user['email'] == email:
                return jsonify({"error": "Email already exists"}), 409
        global next_user_id
        new_user = {
            "id": next_user_id,
            "username": username,
            "email": email,
            "password": hashlib.sha256(password.encode()).hexdigest(),
            "role": data.get('role', 'user'),
            "created_at": datetime.now().isoformat(),
            "active": True
        }
        users[next_user_id] = new_user
        next_user_id += 1
        response_user = {k: v for k, v in new_user.items() if k != 'password'}
        return jsonify(response_user), 201

    @app.route('/api/users/<int:user_id>', methods=['GET'])
    def get_user(user_id):
        if user_id not in users:
            return jsonify({"error": f"User with id {user_id} not found"}), 404
        user = users[user_id]
        response_user = {k: v for k, v in user.items() if k != 'password'}
        return jsonify(response_user), 200

    @app.route('/api/users', methods=['GET'])
    def list_users():
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        role_filter = request.args.get('role')
        active_filter = request.args.get('active')
        if page < 1:
            return jsonify({"error": "Page must be positive"}), 400
        if per_page < 1 or per_page > 100:
            return jsonify({"error": "per_page must be between 1 and 100"}), 400
        filtered_users = list(users.values())
        if role_filter:
            filtered_users = [u for u in filtered_users if u['role'] == role_filter]
        if active_filter is not None:
            active_bool = active_filter.lower() == 'true'
            filtered_users = [u for u in filtered_users if u['active'] == active_bool]
        all_users = [{k: v for k, v in user.items() if k != 'password'} for user in filtered_users]
        start = (page - 1) * per_page
        end = start + per_page
        paginated_users = all_users[start:end]
        return jsonify({
            "users": paginated_users,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": len(all_users),
                "pages": (len(all_users) + per_page - 1) // per_page if all_users else 0
            }
        }), 200

    @app.route('/api/users/<int:user_id>', methods=['PUT'])
    def update_user(user_id):
        if user_id not in users:
            return jsonify({"error": f"User with id {user_id} not found"}), 404
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        user = users[user_id]
        if 'email' in data:
            email = data['email'].strip().lower()
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                return jsonify({"error": "Invalid email format"}), 400
            for uid, u in users.items():
                if uid != user_id and u['email'] == email:
                    return jsonify({"error": "Email already in use"}), 409
            user['email'] = email
        if 'password' in data:
            password = data['password']
            if len(password) < 8:
                return jsonify({"error": "Password must be at least 8 characters"}), 400
            user['password'] = hashlib.sha256(password.encode()).hexdigest()
        if 'active' in data:
            user['active'] = bool(data['active'])
        user['updated_at'] = datetime.now().isoformat()
        response_user = {k: v for k, v in user.items() if k != 'password'}
        return jsonify(response_user), 200

    @app.route('/api/users/<int:user_id>', methods=['DELETE'])
    def delete_user(user_id):
        if user_id not in users:
            return jsonify({"error": f"User with id {user_id} not found"}), 404
        del users[user_id]
        return '', 204

    @app.route('/api/auth/login', methods=['POST'])
    def login():
        client_ip = request.remote_addr or 'unknown'
        if not check_rate_limit(f"login_{client_ip}", limit=10, window=60):
            return jsonify({"error": "Too many login attempts. Please try again later."}), 429
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({"error": "Missing username or password"}), 400
        username = data['username']
        password = data['password']
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        user = None
        for u in users.values():
            if u['username'] == username:
                user = u
                break
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401
        if not user.get('active', True):
            return jsonify({"error": "Account is deactivated"}), 403
        if user['password'] == password_hash:
            token = str(uuid.uuid4())
            tokens[token] = {
                "user_id": user['id'],
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()
            }
            return jsonify({
                "token": token,
                "user_id": user['id'],
                "role": user['role'],
                "expires_in": 86400
            }), 200
        return jsonify({"error": "Invalid credentials"}), 401

    @app.route('/api/auth/logout', methods=['POST'])
    @require_auth
    def logout():
        auth_header = request.headers.get('Authorization', '')
        token = auth_header[7:]
        if token in tokens:
            del tokens[token]
        return jsonify({"message": "Logged out successfully"}), 200

    @app.route('/api/auth/me', methods=['GET'])
    @require_auth
    def get_current_user_info():
        user = request.current_user
        response_user = {k: v for k, v in user.items() if k != 'password'}
        return jsonify(response_user), 200

    @app.route('/api/categories', methods=['GET'])
    def list_categories():
        return jsonify({"categories": list(categories.values())}), 200

    @app.route('/api/categories/<int:category_id>', methods=['GET'])
    def get_category(category_id):
        if category_id not in categories:
            return jsonify({"error": f"Category with id {category_id} not found"}), 404
        return jsonify(categories[category_id]), 200

    @app.route('/api/categories', methods=['POST'])
    @require_admin
    def create_category():
        data = request.get_json()
        if not data or 'name' not in data:
            return jsonify({"error": "Missing required field: name"}), 400
        name = data['name'].strip()
        if len(name) < 2 or len(name) > 100:
            return jsonify({"error": "Category name must be between 2 and 100 characters"}), 400
        for cat in categories.values():
            if cat['name'].lower() == name.lower():
                return jsonify({"error": "Category already exists"}), 409
        global next_category_id
        new_category = {
            "id": next_category_id,
            "name": name,
            "description": data.get('description', '')
        }
        categories[next_category_id] = new_category
        next_category_id += 1
        return jsonify(new_category), 201

    @app.route('/api/categories/<int:category_id>', methods=['DELETE'])
    @require_admin
    def delete_category(category_id):
        if category_id not in categories:
            return jsonify({"error": f"Category with id {category_id} not found"}), 404
        for product in products.values():
            if product['category_id'] == category_id:
                return jsonify({"error": "Cannot delete category with associated products"}), 400
        del categories[category_id]
        return '', 204

    @app.route('/api/products', methods=['GET'])
    def list_products():
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        category_id = request.args.get('category_id', type=int)
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        in_stock = request.args.get('in_stock')
        sort_by = request.args.get('sort_by', 'id')
        sort_order = request.args.get('sort_order', 'asc')
        if page < 1:
            return jsonify({"error": "Page must be positive"}), 400
        if per_page < 1 or per_page > 100:
            return jsonify({"error": "per_page must be between 1 and 100"}), 400
        filtered_products = [p for p in products.values() if p['active']]
        if category_id:
            filtered_products = [p for p in filtered_products if p['category_id'] == category_id]
        if min_price is not None:
            filtered_products = [p for p in filtered_products if p['price'] >= min_price]
        if max_price is not None:
            filtered_products = [p for p in filtered_products if p['price'] <= max_price]
        if in_stock is not None:
            if in_stock.lower() == 'true':
                filtered_products = [p for p in filtered_products if p['stock'] > 0]
            else:
                filtered_products = [p for p in filtered_products if p['stock'] == 0]
        if sort_by in ['id', 'name', 'price', 'stock']:
            reverse = sort_order.lower() == 'desc'
            filtered_products.sort(key=lambda x: x[sort_by], reverse=reverse)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_products = filtered_products[start:end]
        return jsonify({
            "products": paginated_products,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": len(filtered_products),
                "pages": (len(filtered_products) + per_page - 1) // per_page if filtered_products else 0
            }
        }), 200

    @app.route('/api/products/<int:product_id>', methods=['GET'])
    def get_product(product_id):
        if product_id not in products:
            return jsonify({"error": f"Product with id {product_id} not found"}), 404
        product = products[product_id]
        category = categories.get(product['category_id'])
        response = {**product, "category": category}
        return jsonify(response), 200

    @app.route('/api/products', methods=['POST'])
    @require_admin
    def create_product():
        data = request.get_json()
        required = ['name', 'price', 'category_id']
        if not data or not all(k in data for k in required):
            return jsonify({"error": f"Missing required fields: {', '.join(required)}"}), 400
        name = data['name'].strip()
        price = data['price']
        category_id = data['category_id']
        stock = data.get('stock', 0)
        if len(name) < 2 or len(name) > 200:
            return jsonify({"error": "Product name must be between 2 and 200 characters"}), 400
        if not isinstance(price, (int, float)) or price < 0:
            return jsonify({"error": "Price must be a non-negative number"}), 400
        if category_id not in categories:
            return jsonify({"error": f"Category with id {category_id} not found"}), 404
        if not isinstance(stock, int) or stock < 0:
            return jsonify({"error": "Stock must be a non-negative integer"}), 400
        global next_product_id
        new_product = {
            "id": next_product_id,
            "name": name,
            "description": data.get('description', ''),
            "price": round(price, 2),
            "stock": stock,
            "category_id": category_id,
            "created_at": datetime.now().isoformat(),
            "active": True
        }
        products[next_product_id] = new_product
        next_product_id += 1
        return jsonify(new_product), 201

    @app.route('/api/products/<int:product_id>', methods=['PUT'])
    @require_admin
    def update_product(product_id):
        if product_id not in products:
            return jsonify({"error": f"Product with id {product_id} not found"}), 404
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        product = products[product_id]
        if 'name' in data:
            name = data['name'].strip()
            if len(name) < 2 or len(name) > 200:
                return jsonify({"error": "Product name must be between 2 and 200 characters"}), 400
            product['name'] = name
        if 'description' in data:
            product['description'] = data['description']
        if 'price' in data:
            price = data['price']
            if not isinstance(price, (int, float)) or price < 0:
                return jsonify({"error": "Price must be a non-negative number"}), 400
            product['price'] = round(price, 2)
        if 'stock' in data:
            stock = data['stock']
            if not isinstance(stock, int) or stock < 0:
                return jsonify({"error": "Stock must be a non-negative integer"}), 400
            product['stock'] = stock
        if 'category_id' in data:
            if data['category_id'] not in categories:
                return jsonify({"error": f"Category with id {data['category_id']} not found"}), 404
            product['category_id'] = data['category_id']
        if 'active' in data:
            product['active'] = bool(data['active'])
        product['updated_at'] = datetime.now().isoformat()
        return jsonify(product), 200

    @app.route('/api/products/<int:product_id>', methods=['DELETE'])
    @require_admin
    def delete_product(product_id):
        if product_id not in products:
            return jsonify({"error": f"Product with id {product_id} not found"}), 404
        del products[product_id]
        return '', 204

    @app.route('/api/orders', methods=['POST'])
    @require_auth
    def create_order():
        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({"error": "Missing required field: items"}), 400
        items = data['items']
        if not isinstance(items, list) or len(items) == 0:
            return jsonify({"error": "Items must be a non-empty array"}), 400
        order_items = []
        total = 0
        for item in items:
            if 'product_id' not in item or 'quantity' not in item:
                return jsonify({"error": "Each item must have product_id and quantity"}), 400
            product_id = item['product_id']
            quantity = item['quantity']
            if product_id not in products:
                return jsonify({"error": f"Product with id {product_id} not found"}), 404
            product = products[product_id]
            if not product['active']:
                return jsonify({"error": f"Product '{product['name']}' is not available"}), 400
            if not isinstance(quantity, int) or quantity < 1:
                return jsonify({"error": "Quantity must be a positive integer"}), 400
            if quantity > product['stock']:
                return jsonify({"error": f"Insufficient stock for '{product['name']}'. Available: {product['stock']}"}), 400
            item_total = product['price'] * quantity
            order_items.append({
                "product_id": product_id,
                "product_name": product['name'],
                "quantity": quantity,
                "unit_price": product['price'],
                "total": round(item_total, 2)
            })
            total += item_total
        for item in items:
            products[item['product_id']]['stock'] -= item['quantity']
        global next_order_id
        new_order = {
            "id": next_order_id,
            "user_id": request.current_user['id'],
            "items": order_items,
            "total": round(total, 2),
            "status": "pending",
            "shipping_address": data.get('shipping_address', ''),
            "created_at": datetime.now().isoformat()
        }
        orders[next_order_id] = new_order
        next_order_id += 1
        return jsonify(new_order), 201

    @app.route('/api/orders', methods=['GET'])
    @require_auth
    def list_orders():
        user = request.current_user
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status_filter = request.args.get('status')
        if user['role'] == 'admin':
            user_orders = list(orders.values())
        else:
            user_orders = [o for o in orders.values() if o['user_id'] == user['id']]
        if status_filter:
            user_orders = [o for o in user_orders if o['status'] == status_filter]
        user_orders.sort(key=lambda x: x['created_at'], reverse=True)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_orders = user_orders[start:end]
        return jsonify({
            "orders": paginated_orders,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": len(user_orders),
                "pages": (len(user_orders) + per_page - 1) // per_page if user_orders else 0
            }
        }), 200

    @app.route('/api/orders/<int:order_id>', methods=['GET'])
    @require_auth
    def get_order(order_id):
        if order_id not in orders:
            return jsonify({"error": f"Order with id {order_id} not found"}), 404
        order = orders[order_id]
        user = request.current_user
        if user['role'] != 'admin' and order['user_id'] != user['id']:
            return jsonify({"error": "Access denied"}), 403
        return jsonify(order), 200

    @app.route('/api/orders/<int:order_id>/status', methods=['PUT'])
    @require_admin
    def update_order_status(order_id):
        if order_id not in orders:
            return jsonify({"error": f"Order with id {order_id} not found"}), 404
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({"error": "Missing required field: status"}), 400
        valid_statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled']
        new_status = data['status']
        if new_status not in valid_statuses:
            return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400
        order = orders[order_id]
        if order['status'] == 'cancelled':
            return jsonify({"error": "Cannot update cancelled order"}), 400
        if new_status == 'cancelled' and order['status'] not in ['pending', 'processing']:
            return jsonify({"error": "Can only cancel pending or processing orders"}), 400
        if new_status == 'cancelled':
            for item in order['items']:
                if item['product_id'] in products:
                    products[item['product_id']]['stock'] += item['quantity']
        order['status'] = new_status
        order['updated_at'] = datetime.now().isoformat()
        return jsonify(order), 200

    @app.route('/api/search', methods=['GET'])
    def search():
        query = request.args.get('q', '').strip().lower()
        search_type = request.args.get('type', 'all')
        if not query or len(query) < 2:
            return jsonify({"error": "Search query must be at least 2 characters"}), 400
        results = {"users": [], "products": [], "categories": []}
        if search_type in ['all', 'users']:
            results['users'] = [
                {k: v for k, v in u.items() if k != 'password'}
                for u in users.values()
                if query in u['username'].lower() or query in u['email'].lower()
            ][:10]
        if search_type in ['all', 'products']:
            results['products'] = [
                p for p in products.values()
                if p['active'] and (query in p['name'].lower() or query in p.get('description', '').lower())
            ][:10]
        if search_type in ['all', 'categories']:
            results['categories'] = [
                c for c in categories.values()
                if query in c['name'].lower() or query in c.get('description', '').lower()
            ][:10]
        total = len(results['users']) + len(results['products']) + len(results['categories'])
        return jsonify({"query": query, "results": results, "total": total}), 200

    @app.route('/api/stats', methods=['GET'])
    @require_admin
    def get_stats():
        total_users = len(users)
        active_users = sum(1 for u in users.values() if u.get('active', True))
        total_products = len(products)
        active_products = sum(1 for p in products.values() if p['active'])
        total_orders = len(orders)
        total_revenue = sum(o['total'] for o in orders.values() if o['status'] != 'cancelled')
        orders_by_status = {}
        for order in orders.values():
            status = order['status']
            orders_by_status[status] = orders_by_status.get(status, 0) + 1
        low_stock_products = [
            {"id": p['id'], "name": p['name'], "stock": p['stock']}
            for p in products.values()
            if p['active'] and p['stock'] < 10
        ]
        return jsonify({
            "users": {"total": total_users, "active": active_users},
            "products": {"total": total_products, "active": active_products},
            "orders": {"total": total_orders, "by_status": orders_by_status},
            "revenue": {"total": round(total_revenue, 2)},
            "low_stock_products": low_stock_products,
            "categories_count": len(categories)
        }), 200

    @app.route('/api/users/bulk', methods=['POST'])
    @require_admin
    def bulk_create_users():
        data = request.get_json()
        if not data or 'users' not in data:
            return jsonify({"error": "Missing required field: users"}), 400
        users_data = data['users']
        if not isinstance(users_data, list) or len(users_data) == 0:
            return jsonify({"error": "Users must be a non-empty array"}), 400
        if len(users_data) > 50:
            return jsonify({"error": "Maximum 50 users per request"}), 400
        created = []
        errors = []
        for idx, user_data in enumerate(users_data):
            if not all(k in user_data for k in ['username', 'email', 'password']):
                errors.append({"index": idx, "error": "Missing required fields"})
                continue
            username = user_data['username'].strip()
            email = user_data['email'].strip().lower()
            duplicate = False
            for u in users.values():
                if u['username'].lower() == username.lower() or u['email'] == email:
                    duplicate = True
                    break
            for c in created:
                if c['username'].lower() == username.lower() or c['email'] == email:
                    duplicate = True
                    break
            if duplicate:
                errors.append({"index": idx, "error": "Duplicate username or email"})
                continue
            global next_user_id
            new_user = {
                "id": next_user_id,
                "username": username,
                "email": email,
                "password": hashlib.sha256(user_data['password'].encode()).hexdigest(),
                "role": user_data.get('role', 'user'),
                "created_at": datetime.now().isoformat(),
                "active": True
            }
            users[next_user_id] = new_user
            created.append({k: v for k, v in new_user.items() if k != 'password'})
            next_user_id += 1
        return jsonify({
            "created": created,
            "created_count": len(created),
            "errors": errors,
            "error_count": len(errors)
        }), 201 if created else 400

    @app.route('/api/products/<int:product_id>/stock', methods=['PUT'])
    @require_admin
    def update_stock(product_id):
        if product_id not in products:
            return jsonify({"error": f"Product with id {product_id} not found"}), 404
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        product = products[product_id]
        if 'stock' in data:
            stock = data['stock']
            if not isinstance(stock, int) or stock < 0:
                return jsonify({"error": "Stock must be a non-negative integer"}), 400
            product['stock'] = stock
        elif 'adjustment' in data:
            adjustment = data['adjustment']
            if not isinstance(adjustment, int):
                return jsonify({"error": "Adjustment must be an integer"}), 400
            new_stock = product['stock'] + adjustment
            if new_stock < 0:
                return jsonify({"error": "Stock cannot be negative"}), 400
            product['stock'] = new_stock
        else:
            return jsonify({"error": "Must provide either 'stock' or 'adjustment'"}), 400
        product['updated_at'] = datetime.now().isoformat()
        return jsonify({"id": product_id, "name": product['name'], "stock": product['stock']}), 200

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal server error"}), 500

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5050)
