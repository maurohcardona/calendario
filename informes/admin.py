from django.contrib import admin
from .models import Informes

# Register your models here.

@admin.register(Informes)
class InformesAdmin(admin.ModelAdmin):
    list_display = ('nombre_archivo', 'get_iden_paciente', 'get_nombre_paciente', 
                    'numero_orden', 'numero_protocolo', 'estado', 'fecha_envio', 'intentos_envio')
    list_filter = ('estado', 'fecha_creacion', 'fecha_envio')
    search_fields = ('paciente__iden', 'paciente__nombre', 'paciente__apellido', 
                     'numero_orden', 'numero_protocolo', 'email_destino')
    readonly_fields = ('fecha_creacion', 'fecha_envio', 'intentos_envio', 'mensaje_error')
    ordering = ['-fecha_creacion']
    
    fieldsets = (
        ('Información del Paciente', {
            'fields': ('paciente', 'id_turno')
        }),
        ('Datos del Informe', {
            'fields': ('numero_orden', 'numero_protocolo', 'nombre_archivo')
        }),
        ('Estado del Envío', {
            'fields': ('estado', 'email_destino', 'fecha_creacion', 'fecha_envio', 
                      'intentos_envio', 'mensaje_error')
        }),
    )
    
    def get_iden_paciente(self, obj):
        """Muestra la identificación del paciente"""
        return obj.paciente.iden if obj.paciente else '-'
    get_iden_paciente.short_description = 'Identificación'
    get_iden_paciente.admin_order_field = 'paciente__iden'
    
    def get_nombre_paciente(self, obj):
        """Muestra el nombre completo del paciente"""
        if obj.paciente:
            return f"{obj.paciente.apellido}, {obj.paciente.nombre}"
        return '-'
    get_nombre_paciente.short_description = 'Paciente'
    get_nombre_paciente.admin_order_field = 'paciente__apellido'
    
    actions = ['marcar_como_pendiente', 'reintentar_envio']
    
    def marcar_como_pendiente(self, request, queryset):
        """Marca informes seleccionados como pendientes"""
        count = queryset.update(estado='PENDIENTE')
        self.message_user(request, f'{count} informe(s) marcado(s) como pendiente.')
    marcar_como_pendiente.short_description = "Marcar como pendiente"
    
    def reintentar_envio(self, request, queryset):
        """Reinicia el contador de intentos para volver a enviar"""
        count = queryset.filter(estado='ERROR').update(estado='PENDIENTE', intentos_envio=0, mensaje_error='')
        self.message_user(request, f'{count} informe(s) preparado(s) para reenvío.')
    reintentar_envio.short_description = "Reintentar envío"
