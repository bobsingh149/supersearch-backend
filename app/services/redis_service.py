import redis
import json
import logging
from typing import Optional, Any
import hashlib
from app.core.appsettings import app_settings

logger = logging.getLogger(__name__)

class RedisService:
    def __init__(self, host: str = None, port: int = None, db: int = None, password: Optional[str] = None):
        """
        Initialize Redis service with connection parameters.
        
        Args:
            host: Redis host address (defaults to settings)
            port: Redis port (defaults to settings)
            db: Redis database number (defaults to settings)
            password: Redis password (optional, defaults to settings)
        """
        # Use settings if not provided
        if host is None:
            host = app_settings.redis.host
        if port is None:
            port = app_settings.redis.port
        if db is None:
            db = app_settings.redis.db
        if password is None:
            password = app_settings.redis.password
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test the connection
            self.redis_client.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        """
        Generate a cache key based on the prefix and parameters.
        
        Args:
            prefix: Cache key prefix
            **kwargs: Parameters to include in the cache key
            
        Returns:
            Cache key string
        """
        # Create a sorted string of key-value pairs
        sorted_params = sorted(kwargs.items())
        param_string = "&".join([f"{k}={v}" for k, v in sorted_params])
        
        # Create hash of the parameters for a shorter key
        param_hash = hashlib.md5(param_string.encode()).hexdigest()
        
        return f"{prefix}:{param_hash}"
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        if not self.redis_client:
            return None
            
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting value from Redis: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 60) -> bool:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: 60 seconds)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False
            
        try:
            serialized_value = json.dumps(value)
            return self.redis_client.setex(key, ttl, serialized_value)
        except Exception as e:
            logger.error(f"Error setting value in Redis: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False
            
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Error deleting value from Redis: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists, False otherwise
        """
        if not self.redis_client:
            return False
            
        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Error checking key existence in Redis: {e}")
            return False
    
    def get_or_set(self, key: str, value_func, ttl: int = 60) -> Optional[Any]:
        """
        Get value from cache, or set it if not found.

        Args:
            key: Cache key
            value_func: Function to call to get the value if not cached
            ttl: Time to live in seconds (default: 60 seconds)

        Returns:
            Cached or computed value
        """
        # Try to get from cache first
        cached_value = self.get(key)
        if cached_value is not None:
            logger.info(f"Cache hit for key: {key}")
            return cached_value

        # If not in cache, compute the value
        logger.info(f"Cache miss for key: {key}")
        try:
            computed_value = value_func()
            if computed_value is not None:
                self.set(key, computed_value, ttl)
            return computed_value
        except Exception as e:
            logger.error(f"Error computing value for cache: {e}")
            return None

    def hget(self, key: str, field: str) -> Optional[Any]:
        """
        Get the value of a field in a hash.

        Args:
            key: Hash key
            field: Field name

        Returns:
            Field value or None if not found
        """
        if not self.redis_client:
            return None

        try:
            value = self.redis_client.hget(key, field)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting hash field from Redis: {e}")
            return None

    def hset(self, key: str, field: str, value: Any) -> bool:
        """
        Set the value of a field in a hash.

        Args:
            key: Hash key
            field: Field name
            value: Value to set

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            serialized_value = json.dumps(value)
            return bool(self.redis_client.hset(key, field, serialized_value))
        except Exception as e:
            logger.error(f"Error setting hash field in Redis: {e}")
            return False

    def hmget(self, key: str, fields: list) -> Optional[dict]:
        """
        Get multiple fields from a hash.

        Args:
            key: Hash key
            fields: List of field names

        Returns:
            Dictionary of field-value pairs or None if error
        """
        if not self.redis_client:
            return None

        try:
            values = self.redis_client.hmget(key, fields)
            if values:
                result = {}
                for field, value in zip(fields, values):
                    if value is not None:
                        result[field] = json.loads(value)
                return result
            return {}
        except Exception as e:
            logger.error(f"Error getting multiple hash fields from Redis: {e}")
            return None

    def hmset(self, key: str, mapping: dict) -> bool:
        """
        Set multiple fields in a hash.

        Args:
            key: Hash key
            mapping: Dictionary of field-value pairs

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            serialized_mapping = {k: json.dumps(v) for k, v in mapping.items()}
            return bool(self.redis_client.hmset(key, serialized_mapping))
        except Exception as e:
            logger.error(f"Error setting multiple hash fields in Redis: {e}")
            return False

    def hgetall(self, key: str) -> Optional[dict]:
        """
        Get all fields and values from a hash.

        Args:
            key: Hash key

        Returns:
            Dictionary of all field-value pairs or None if error
        """
        if not self.redis_client:
            return None

        try:
            result = self.redis_client.hgetall(key)
            if result:
                return {k: json.loads(v) for k, v in result.items()}
            return {}
        except Exception as e:
            logger.error(f"Error getting all hash fields from Redis: {e}")
            return None

    def hdel(self, key: str, *fields) -> int:
        """
        Delete fields from a hash.

        Args:
            key: Hash key
            *fields: Field names to delete

        Returns:
            Number of fields deleted
        """
        if not self.redis_client:
            return 0

        try:
            return self.redis_client.hdel(key, *fields)
        except Exception as e:
            logger.error(f"Error deleting hash fields from Redis: {e}")
            return 0

    def hkeys(self, key: str) -> Optional[list]:
        """
        Get all field names in a hash.

        Args:
            key: Hash key

        Returns:
            List of field names or None if error
        """
        if not self.redis_client:
            return None

        try:
            return self.redis_client.hkeys(key)
        except Exception as e:
            logger.error(f"Error getting hash keys from Redis: {e}")
            return None

    def hvals(self, key: str) -> Optional[list]:
        """
        Get all values in a hash.

        Args:
            key: Hash key

        Returns:
            List of values (deserialized) or None if error
        """
        if not self.redis_client:
            return None

        try:
            values = self.redis_client.hvals(key)
            if values:
                return [json.loads(v) for v in values]
            return []
        except Exception as e:
            logger.error(f"Error getting hash values from Redis: {e}")
            return None

    def hexists(self, key: str, field: str) -> bool:
        """
        Check if a field exists in a hash.

        Args:
            key: Hash key
            field: Field name

        Returns:
            True if field exists, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            return bool(self.redis_client.hexists(key, field))
        except Exception as e:
            logger.error(f"Error checking hash field existence in Redis: {e}")
            return False

# Global Redis instance
redis_service = RedisService()

def get_redis_service() -> RedisService:
    """
    Get the global Redis service instance.
    
    Returns:
        RedisService instance
    """
    return redis_service 