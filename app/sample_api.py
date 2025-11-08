from flask import Flask, request, jsonify
from datetime import datetime
import hashlib

# In-memory storage (global for simplicity)
users = {
    1: {"id": 1, "username": "admin", "email": "admin@example.com", "password": hashlib.sha256("admin123".encode()).hexdigest(), "created_at": "2024-01-01T00:00:00"},
    2: {"id": 2, "username": "user1", "email": "user1@example.com", "password": hashlib.sha256("password123".encode()).hexdigest(), "created_at": "2024-01-02T00:00:00"}
}
next_id = 3

def create_app():
    """Application factory pattern for Flask"""
    app = Flask(__name__)
    app.config['TESTING'] = False
    
    # Register all routes
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "User Management API"
        }), 200

    @app.route('/api/users', methods=['POST'])
    def create_user():
        """Create a new user"""
        data = request.get_json()
        
        # Validation
        if not data or 'username' not in data or 'email' not in data or 'password' not in data:
            return jsonify({"error": "Missing required fields: username, email, password"}), 400
        
        username = data['username'].strip()
        email = data['email'].strip()
        password = data['password']
        
        if len(username) < 3 or len(username) > 50:
            return jsonify({"error": "Username must be between 3 and 50 characters"}), 400
        
        if '@' not in email or '.' not in email:
            return jsonify({"error": "Invalid email format"}), 400
        
        if len(password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400
        
        # Check for duplicate username or email
        for user in users.values():
            if user['username'] == username:
                return jsonify({"error": "Username already exists"}), 409
            if user['email'] == email:
                return jsonify({"error": "Email already exists"}), 409
        
        global next_id
        new_user = {
            "id": next_id,
            "username": username,
            "email": email,
            "password": hashlib.sha256(password.encode()).hexdigest(),
            "created_at": datetime.now().isoformat()
        }
        users[next_id] = new_user
        next_id += 1
        
        # Return user without password
        response_user = {k: v for k, v in new_user.items() if k != 'password'}
        return jsonify(response_user), 201

    @app.route('/api/users/<int:user_id>', methods=['GET'])
    def get_user(user_id):
        """Get user by ID"""
        if user_id not in users:
            return jsonify({"error": f"User with id {user_id} not found"}), 404
        
        user = users[user_id]
        response_user = {k: v for k, v in user.items() if k != 'password'}
        return jsonify(response_user), 200

    @app.route('/api/users', methods=['GET'])
    def list_users():
        """List all users with pagination"""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        if per_page > 100:
            per_page = 100
        
        all_users = [
            {k: v for k, v in user.items() if k != 'password'}
            for user in users.values()
        ]
        
        start = (page - 1) * per_page
        end = start + per_page
        paginated_users = all_users[start:end]
        
        return jsonify({
            "users": paginated_users,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": len(all_users),
                "pages": (len(all_users) + per_page - 1) // per_page
            }
        }), 200

    @app.route('/api/users/<int:user_id>', methods=['PUT'])
    def update_user(user_id):
        """Update user information"""
        if user_id not in users:
            return jsonify({"error": f"User with id {user_id} not found"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        user = users[user_id]
        
        # Update email if provided
        if 'email' in data:
            email = data['email'].strip()
            if '@' not in email or '.' not in email:
                return jsonify({"error": "Invalid email format"}), 400
            
            # Check for duplicate email
            for uid, u in users.items():
                if uid != user_id and u['email'] == email:
                    return jsonify({"error": "Email already in use"}), 409
            
            user['email'] = email
        
        # Update password if provided
        if 'password' in data:
            password = data['password']
            if len(password) < 8:
                return jsonify({"error": "Password must be at least 8 characters"}), 400
            user['password'] = hashlib.sha256(password.encode()).hexdigest()
        
        user['updated_at'] = datetime.now().isoformat()
        
        response_user = {k: v for k, v in user.items() if k != 'password'}
        return jsonify(response_user), 200

    @app.route('/api/users/<int:user_id>', methods=['DELETE'])
    def delete_user(user_id):
        """Delete a user"""
        if user_id not in users:
            return jsonify({"error": f"User with id {user_id} not found"}), 404
        
        del users[user_id]
        return '', 204

    @app.route('/api/auth/login', methods=['POST'])
    def login():
        """
        Login endpoint - CONTAINS INTENTIONAL BUG
        
        BUG: Always returns 401 even for valid credentials
        Expected: Should return 200 with token for valid credentials
        """
        data = request.get_json()
        
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({"error": "Missing username or password"}), 400
        
        username = data['username']
        password = data['password']
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Find user by username
        user = None
        for u in users.values():
            if u['username'] == username:
                user = u
                break
        
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401
        
        # INTENTIONAL BUG: Always return 401 even when password matches
        # This simulates an application defect for testing
        # Correct code would be:
        # if user['password'] == password_hash:
        #     return jsonify({"token": "fake-jwt-token", "user_id": user['id']}), 200
        
        # BUG: Always returns 401
        return jsonify({"error": "Invalid credentials"}), 401
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
