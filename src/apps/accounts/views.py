from adrf.views import APIView as AsyncAPIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from adrf import generics
from .models import User
from rest_framework.permissions import AllowAny
from .serializer import RegisterSerializer, LoginSerializer
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    queryset = User.objects.all()
    serializer_class = RegisterSerializer


class LoginView(AsyncAPIView):
    async def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data.get("email")
        password = serializer.validated_data.get("password")
        try:
            user = await User.objects.aget(email=email)
        except User.DoesNotExist:
            raise AuthenticationFailed("Wrong email or password")
        if not user.is_active or not await user.acheck_password(password):
            raise AuthenticationFailed("Wrong email or password")
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )
    
