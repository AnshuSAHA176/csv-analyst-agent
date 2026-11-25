from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication


@database_sync_to_async
def get_user_from_token(token):
    try:
        jwt_auth = JWTAuthentication()
        validated = jwt_auth.get_validated_token(token)
        print(f"validated :- {validated}")
        print("User:- ", jwt_auth.get_user(validated))
        return jwt_auth.get_user(validated)
    except Exception:
        return AnonymousUser()


class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        print(scope)
        query_params = parse_qs(scope.get("query_string", b"").decode())
        print("query_params", query_params)
        token = query_params.get("token", [None])[0]
        scope["user"] = await get_user_from_token(token) if token else AnonymousUser
        return await self.inner(scope, receive, send)
