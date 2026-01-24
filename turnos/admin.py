from django.contrib import admin
from .models import Cupo, Turno, Agenda, Coordinados, Feriados


@admin.register(Agenda)
class AgendaAdmin(admin.ModelAdmin):
	list_display = ('name', 'slug', 'color')
	prepopulated_fields = {"slug": ("name",)}


@admin.register(Coordinados)
class CoordinadosAdmin(admin.ModelAdmin):
	list_display = ('id_turno', 'get_dni', 'get_apellido', 'get_nombre', 'fecha_coordinacion')
	list_filter = ('fecha_coordinacion',)
	search_fields = ('dni__iden', 'dni__apellido', 'dni__nombre')
	readonly_fields = ('fecha_coordinacion',)
	ordering = ('-fecha_coordinacion', 'id_turno')
	
	def get_dni(self, obj):
		return obj.dni.iden if obj.dni else '-'
	get_dni.short_description = 'DNI'
	get_dni.admin_order_field = 'dni__iden'
	
	def get_apellido(self, obj):
		return obj.dni.apellido if obj.dni else '-'
	get_apellido.short_description = 'Apellido'
	get_apellido.admin_order_field = 'dni__apellido'
	
	def get_nombre(self, obj):
		return obj.dni.nombre if obj.dni else '-'
	get_nombre.short_description = 'Nombre'
	get_nombre.admin_order_field = 'dni__nombre'



@admin.register(Cupo)
class CupoAdmin(admin.ModelAdmin):
	list_display = ('agenda', 'fecha', 'cantidad_total')
	list_filter = ('agenda',)
	actions = ['crear_cupos_rango']

	def crear_cupos_rango(self, request, queryset):
		"""Admin action: crear cupos de lunes a viernes en un rango de fechas con cantidad configurable."""
		from django.shortcuts import render
		from django import forms
		from datetime import datetime, timedelta
		from django.contrib import messages

		class _CreateCuposForm(forms.Form):
			agenda = forms.ModelChoiceField(queryset=Agenda.objects.all(), label="Agenda")
			start = forms.DateField(required=True, widget=forms.DateInput(attrs={'type':'date'}), label="Desde")
			end = forms.DateField(required=True, widget=forms.DateInput(attrs={'type':'date'}), label="Hasta")
			cantidad = forms.IntegerField(required=True, initial=5, min_value=1, label="Cantidad de cupos")

		if 'apply' in request.POST:
			form = _CreateCuposForm(request.POST)
			if form.is_valid():
				start = form.cleaned_data['start']
				end = form.cleaned_data['end']
				cantidad = form.cleaned_data['cantidad']
				agenda = form.cleaned_data['agenda']
				
				total_created = 0
				total_skipped = 0
				
				# Iterar desde start hasta end, solo de lunes a viernes
				cur = start
				while cur <= end:
					# weekday(): 0=Lunes, 1=Martes, ..., 4=Viernes, 5=Sábado, 6=Domingo
					if cur.weekday() < 5:  # Solo lunes a viernes
						obj, created = Cupo.objects.get_or_create(
							agenda=agenda,
							fecha=cur,
							defaults={'cantidad_total': cantidad}
						)
						if created:
							total_created += 1
						else:
							total_skipped += 1
					cur += timedelta(days=1)

				messages.success(request, f"✅ Cupos creados: {total_created} nuevos (lunes-viernes). Existentes omitidos: {total_skipped}. Rango: {start} a {end}.")
				return None
		else:
			form = _CreateCuposForm()

		return render(request, 'admin/turnos/cupo_create_range.html', {
			'form': form,
			'title': 'Crear Cupos en Rango de Fechas (Lunes-Viernes)'
		})

	crear_cupos_rango.short_description = "Crear cupos en rango de fechas (Lunes-Viernes)"


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
	list_display = ('agenda', 'fecha', 'get_dni', 'usuario', 'creado')
	list_filter = ('agenda', 'fecha', 'medico')
	search_fields = ('dni__iden', 'dni__apellido', 'dni__nombre', 'medico__nombre')
	readonly_fields = ('creado',)
	fieldsets = (
		('Información del Paciente', {
			'fields': ('dni',)
		}),
		('Turno', {
			'fields': ('agenda', 'fecha', 'medico')
		}),
		('Información Adicional', {
			'fields': ('determinaciones', 'nota_interna')
		}),
		('Auditoría', {
			'fields': ('usuario', 'creado'),
			'classes': ('collapse',)
		}),
	)
	
	def get_search_results(self, request, queryset, search_term):
		"""Personalizar búsqueda para incluir búsqueda de médicos."""
		queryset, use_distinct = super().get_search_results(request, queryset, search_term)
		return queryset, use_distinct

	def get_dni(self, obj):
		return obj.dni.iden if obj.dni else '-'
	get_dni.short_description = 'DNI'
	get_dni.admin_order_field = 'dni__iden'


@admin.register(Feriados)
class FeriadosAdmin(admin.ModelAdmin):
	list_display = ('fecha', 'descripcion')
	list_filter = ('fecha',)
	search_fields = ('descripcion',)
	ordering = ('-fecha',)



