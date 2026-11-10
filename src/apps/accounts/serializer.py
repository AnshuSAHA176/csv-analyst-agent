from adrf import serializers
from .models import User
from django.contrib.auth import authenticate

class RegisterSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["email", "password", "role", "full_name"]
        extra_kwargs = {
            "password": {
                "write_only": True,
                "min_length": 5,
            }
        }

    def validate_email(self, value):
        return value.lower().strip()

    def validate_role(self, value):
        if value == User.RoleChoices.BOSS:
            raise serializers.ValidationError(
                "You cannot register as a boss."
            )
        return value

    async def acreate(self, validated_data):
        return await User.objects.acreate_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(min_length=5)