from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import (
    User, Subcomando, Escuela, Mesa,
    Eleccion, CargoPostulacion, Partido, PartidoPostulacion,
    VotoMesaCargo, VotoMesaEspecial, ResumenMesa
)
from .forms import CustomUserCreationForm, CustomUserChangeForm

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User

    list_display = ("username", "role", "escuela", "is_active", "is_staff", "last_login")
    list_filter  = ("role", "is_active", "is_staff", "escuela")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("username",)
    autocomplete_fields = ("escuela",)
    filter_horizontal = ("groups", "user_permissions")

    # ===== Vista "Cambiar usuario" =====
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Información personal", {"fields": ("first_name", "last_name", "email")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas importantes", {"fields": ("last_login", "date_joined")}),
        ("Datos electorales", {"fields": ("role", "escuela")}),
    )

    # ===== Vista "Agregar usuario" =====
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            # IMPORTANTe: estos campos deben existir en CustomUserCreationForm
            "fields": ("username", "password1", "password2", "role", "escuela", "is_active", "is_staff"),
        }),
    )

# --- el resto de tus ModelAdmin queda igual ---
@admin.register(Subcomando)
class SubcomandoAdmin(admin.ModelAdmin):
    search_fields = ("nombre_subcomando",)
    list_display = ("id", "nombre_subcomando")
    ordering = ("nombre_subcomando",)

class MesaInline(admin.TabularInline):
    model = Mesa
    extra = 0
    fields = ("numero_mesa", "escrutada")
    ordering = ("numero_mesa",)

@admin.register(Escuela)
class EscuelaAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre_escuela", "subcomando")
    list_filter  = ("subcomando",)
    search_fields = ("nombre_escuela",)
    autocomplete_fields = ("subcomando",)
    inlines = [MesaInline]
    ordering = ("nombre_escuela",)

@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    list_display = ("id", "numero_mesa", "escuela", "escrutada")
    list_filter  = ("escrutada", "escuela__subcomando")
    search_fields = ("numero_mesa", "escuela__nombre_escuela")
    autocomplete_fields = ("escuela",)
    ordering = ("numero_mesa",)

@admin.register(Eleccion)
class EleccionAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre_eleccion", "tipo")
    list_filter  = ("tipo",)
    search_fields = ("nombre_eleccion",)
    ordering = ("id",)

@admin.register(CargoPostulacion)
class CargoPostulacionAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre_postulacion", "tipo", "eleccion")
    list_filter  = ("tipo", "eleccion")
    search_fields = ("nombre_postulacion",)
    autocomplete_fields = ("eleccion",)
    ordering = ("id",)

@admin.register(Partido)
class PartidoAdmin(admin.ModelAdmin):
    list_display = ("numero_lista", "nombre_partido", "sigla")
    search_fields = ("nombre_partido", "sigla", "numero_lista")
    ordering = ("numero_lista",)

@admin.register(PartidoPostulacion)
class PartidoPostulacionAdmin(admin.ModelAdmin):
    list_display = ("id", "partido", "cargo_postulacion")
    list_filter  = ("cargo_postulacion__eleccion", "cargo_postulacion__tipo")
    search_fields = ("partido__nombre_partido", "cargo_postulacion__nombre_postulacion")
    autocomplete_fields = ("partido", "cargo_postulacion")
    ordering = ("id",)

@admin.register(VotoMesaCargo)
class VotoMesaCargoAdmin(admin.ModelAdmin):
    list_display = ("id", "mesa", "partido_postulacion", "votos")
    list_filter  = ("mesa__escrutada", "partido_postulacion__cargo_postulacion")
    search_fields = ("mesa__numero_mesa", "partido_postulacion__partido__nombre_partido")
    autocomplete_fields = ("mesa", "partido_postulacion")
    ordering = ("id",)

@admin.register(VotoMesaEspecial)
class VotoMesaEspecialAdmin(admin.ModelAdmin):
    list_display = ("id", "mesa", "tipo", "votos")
    list_filter  = ("tipo", "mesa__escrutada")
    search_fields = ("mesa__numero_mesa",)
    autocomplete_fields = ("mesa",)
    ordering = ("id",)

@admin.register(ResumenMesa)
class ResumenMesaAdmin(admin.ModelAdmin):
    list_display = ("id", "mesa", "electores_votaron", "sobres_encontrados", "diferencia", "escrutada")
    list_filter  = ("escrutada",)
    search_fields = ("mesa__numero_mesa",)
    autocomplete_fields = ("mesa",)
    ordering = ("id",)
