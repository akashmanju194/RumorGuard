"""
Authentication Service: Handles password hashing, verification, and auth checks.
Uses bcrypt directly for secure password management.
"""
import bcrypt

class AuthService:
    """Handles user authentication and password operations."""

    def __init__(self):
        """Initialize authentication service."""
        pass

    def hash_password(self, password: str) -> str:
        """
        Hash a plaintext password using bcrypt.
        
        Args:
            password: Plaintext password to hash
            
        Returns:
            Hashed password string
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a plaintext password against its hash.
        
        Args:
            plain_password: Plaintext password to verify
            hashed_password: Hashed password from database
            
        Returns:
            True if password matches, False otherwise
        """
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )

# Global instance
auth_service = AuthService()
