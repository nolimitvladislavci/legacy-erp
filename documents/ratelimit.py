from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse
import time


def rate_limit(max_requests, window_seconds, key_func=None):
    """Simple rate limiter using Django cache (Redis-backed)."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if key_func:
                rl_key = key_func(request)
            else:
                rl_key = (
                    f"rl:{request.user.id}"
                    if request.user.is_authenticated
                    else f"rl:anon:{request.META.get('REMOTE_ADDR', 'unknown')}"
                )

            cache_key = f"ratelimit:{view_func.__name__}:{rl_key}"

            # Get current window data
            now = time.time()

            # Simple counter approach
            count_key = f"{cache_key}:count"
            reset_key = f"{cache_key}:reset"

            reset_at = cache.get(reset_key)
            if reset_at is None or now > reset_at:
                cache.set(count_key, 1, window_seconds)
                cache.set(reset_key, now + window_seconds, window_seconds)
                return view_func(request, *args, **kwargs)

            count = cache.get(count_key, 0)
            if count >= max_requests:
                retry_after = int(reset_at - now) + 1
                response = JsonResponse(
                    {
                        "error": "Previše zahtjeva. Pokušajte ponovno za {} sekundi.".format(
                            retry_after
                        )
                    },
                    status=429,
                )
                response["Retry-After"] = str(retry_after)
                return response

            cache.incr(count_key)
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
