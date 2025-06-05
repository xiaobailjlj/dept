import redis
import json
import logging

class RedisCache:
    def __init__(self, host='localhost', port=6379, db=0, password=None, logger=None):
        """Initialize Redis cache"""
        self.logger = logger
        try:
            self.redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True
            )
            # Test connection
            self.logger.info(f"Connecting to Redis at {host}:{port}")
            self.redis.ping()
            self.logger.info(f"Redis connected: {host}:{port}")
        except Exception as e:
            self.logger.error(f"Redis connection failed: {e}")
            raise

    def get(self, key):
        """Get from cache"""
        try:
            data = self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            self.logger.error(f"Cache get error: {e}")
            return None

    def set(self, key, value, timeout=3600):
        """Set in cache with TTL"""
        try:
            data = json.dumps(value, default=str)
            return self.redis.setex(key, timeout, data)
        except Exception as e:
            self.logger.error(f"Cache set error: {e}")
            return False

    def clear_all(self):
        """Clear all cache"""
        try:
            return self.redis.flushdb()
        except Exception as e:
            self.logger.error(f"Cache clear error: {e}")
            return False

    def stats(self):
        """Get cache stats"""
        try:
            info = self.redis.info()
            return {
                'connected': True,
                'used_memory': info.get('used_memory_human'),
                'total_keys': self.redis.dbsize()
            }
        except Exception as e:
            return {'connected': False, 'error': str(e)}

    def health(self):
        """Check health"""
        try:
            self.redis.ping()
            return {'status': 'healthy'}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}