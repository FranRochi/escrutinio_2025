from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        # Campos que estarán en el formulario de "Agregar usuario"
        fields = ("username", "password1", "password2", "role", "celular", "escuela", "is_active", "is_staff")

class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        # Campos visibles en "Cambiar usuario"
        fields = (
            "username", "first_name", "last_name", "email",
            "role", "escuela", "celular",
            "is_active", "is_staff", "is_superuser", "groups", "user_permissions"
        )
