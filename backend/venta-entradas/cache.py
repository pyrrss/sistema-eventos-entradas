import os
import json
import redis

_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
_client = redis.Redis.from_url(
    _url,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)

TTL_EVENTOS = 60 # eventos se actualizan cada minuto
TTL_SECCIONES = 15 # secciones de eventos se actualizan cada 15 segundos


def get(key):
    # se obtiene el valor en cache
    try:
        raw = _client.get(key)
        return json.loads(raw) if raw else None
    except (redis.RedisError, ValueError):
        return None


def set_json(key, value, ttl):
    # se cachea valor en redis
    try:
        _client.set(key, json.dumps(value), ex=ttl)
    except redis.RedisError:
        pass


def delete_pattern(pattern):
    # invalidación de cache
    try:
        for k in _client.scan_iter(match=pattern, count=100):
            _client.delete(k)
    except redis.RedisError:
        pass
