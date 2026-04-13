from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

UserModel = get_user_model()


class EmailOrUsernameBackend(ModelBackend):
    """Dozvoljava login putem emaila ILI usernamea."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        # Probaj prvo po usernameu (default)
        try:
            user = UserModel.objects.get(username=username)
        except UserModel.DoesNotExist:
            # Probaj po emailu
            try:
                user = UserModel.objects.get(email__iexact=username)
            except (UserModel.DoesNotExist, UserModel.MultipleObjectsReturned):
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
