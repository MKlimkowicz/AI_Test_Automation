from typing import List, Optional
from datetime import datetime

class User:
    def __init__(self, user_id: int, username: str, email: str):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.created_at = datetime.now()
    
    def to_dict(self) -> dict:
        return {
            "id": self.user_id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat()
        }

class UserRepository:
    def __init__(self):
        self.users: List[User] = []
        self.next_id = 1
    
    def create_user(self, username: str, email: str) -> User:
        user = User(self.next_id, username, email)
        self.users.append(user)
        self.next_id += 1
        return user
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        for user in self.users:
            if user.user_id == user_id:
                return user
        return None
    
    def get_all_users(self) -> List[User]:
        return self.users
    
    def update_user(self, user_id: int, username: str = None, email: str = None) -> Optional[User]:
        user = self.get_user_by_id(user_id)
        if user:
            if username:
                user.username = username
            if email:
                user.email = email
        return user
    
    def delete_user(self, user_id: int) -> bool:
        user = self.get_user_by_id(user_id)
        if user:
            self.users.remove(user)
            return True
        return False

def validate_email(email: str) -> bool:
    return "@" in email and "." in email.split("@")[1]

def validate_username(username: str) -> bool:
    return len(username) >= 3 and username.isalnum()

