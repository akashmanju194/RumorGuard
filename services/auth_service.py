"""
Authentication Service: Handles password hashing, verification, and auth checks.
Uses passlib with bcrypt for secure password management.
"""
from passlib.context import CryptContext

class AuthService:
    """Handles user authentication and password operations."""

    def __init__(self):
        """Initialize password context with bcrypt scheme."""
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(self, password: str) -> str:
        """
        Hash a plaintext password using bcrypt.
        
        Args:
            password: Plaintext password to hash
            
        Returns:
            Hashed password string
        """
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a plaintext password against its hash.
        
        Args:
            plain_password: Plaintext password to verify
            hashed_password: Hashed password from database
            
        Returns:
            True if password matches, False otherwise
        """
        return self.pwd_context.verify(plain_password, hashed_password)

# Global instance
auth_service = AuthService()
