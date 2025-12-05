from django.contrib import admin
from .models import Cupo, Turno, CapacidadDia, Agenda, TurnoMensual


@admin.register(Agenda)
class AgendaAdmin(admin.ModelAdmin):
	list_display = ('name', 'slug', 'color')
	prepopulated_fields = {"slug": ("name",)}


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
	list_display = ('agenda', 'fecha', 'nombre', 'dni', 'creado')
	list_filter = ('agenda', 'fecha')


@admin.register(CapacidadDia)
class CapacidadDiaAdmin(admin.ModelAdmin):
	list_display = ('agenda', 'fecha', 'capacidad')
	list_filter = ('agenda',)

# Registered models so admins can manage daily capacities and agendas

from .models import WeeklyAvailability


@admin.register(WeeklyAvailability)
class WeeklyAvailabilityAdmin(admin.ModelAdmin):
	list_display = ('agenda', 'weekday', 'capacidad', 'active', 'rango_display')
	list_filter = ('agenda', 'weekday', 'active')
	fieldsets = (
		('Información básica', {
			'fields': ('agenda', 'weekday', 'capacidad', 'active')
		}),
		('Rango de fechas (opcional)', {
			'fields': ('desde_fecha', 'hasta_fecha'),
			'description': 'Deja en blanco para aplicar indefinidamente. Si especificas un rango, esta disponibilidad solo se aplicará dentro de esas fechas.'
		}),
	)
	actions = ['create_cupos_for_range']

	def rango_display(self, obj):
		if obj.desde_fecha or obj.hasta_fecha:
			desde = obj.desde_fecha or 'inicio'
			hasta = obj.hasta_fecha or 'fin'
			return f"{desde} → {hasta}"
		return "Sin rango"
	rango_display.short_description = 'Rango'

	def create_cupos_for_range(self, request, queryset):
		"""Admin action: prompt for start/end dates and then create Cupo records
		for each WeeklyAvailability selected, filling all dates in the range where the weekday matches."""
		from django.shortcuts import render, redirect
		from django import forms
		from django.urls import path
		from datetime import datetime, timedelta
		from django.contrib import messages

		class _RangeForm(forms.Form):
			_selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
			start = forms.DateField(required=True, widget=forms.DateInput(attrs={'type':'date'}))
			end = forms.DateField(required=True, widget=forms.DateInput(attrs={'type':'date'}))

		if 'apply' in request.POST:
			form = _RangeForm(request.POST)
			if form.is_valid():
				start = form.cleaned_data['start']
				end = form.cleaned_data['end']
				total_created = 0
				total_skipped = 0
				for wa in queryset:
					agenda = wa.agenda
					# iterate dates strictly within the range
					cur = start
					while cur <= end:
						if cur.weekday() == wa.weekday and wa.active:
							# create Cupo for this agenda+date only if it does not exist
							Cupo = self.model._meta.apps.get_model('turnos', 'Cupo')
							obj, created = Cupo.objects.get_or_create(agenda=agenda, fecha=cur, defaults={'cantidad_total': wa.capacidad})
							if created:
								total_created += 1
							else:
								total_skipped += 1
						cur += timedelta(days=1)

				messages.success(request, f"Cupos creados: {total_created} nuevos. Existentes omitidos: {total_skipped}. Rango: {start} a {end}.")
				return None
		else:
			form = _RangeForm(initial={'_selected_action': queryset.values_list('pk', flat=True)})

		return render(request, 'admin/turnos/weeklyavailability_create_range.html', {'queryset': queryset, 'form': form, 'title': 'Crear Cupos desde rango de fechas'})

	create_cupos_for_range.short_description = "Crear/Actualizar Cupos desde rango de fechas (para las entries seleccionadas)"


@admin.register(TurnoMensual)
class TurnoMensualAdmin(admin.ModelAdmin):
	list_display = ('agenda', 'desde_fecha', 'hasta_fecha', 'cantidad', 'estado_display', 'creado')
	list_filter = ('agenda', 'aplicado', 'creado')
	readonly_fields = ('aplicado', 'creado')
	fieldsets = (
		('Información', {
			'fields': ('agenda', 'desde_fecha', 'hasta_fecha', 'cantidad')
		}),
		('Estado', {
			'fields': ('aplicado', 'creado'),
			'classes': ('collapse',)
		}),
	)
	actions = ['aplicar_turnos_mensuales']

	def estado_display(self, obj):
		if obj.aplicado:
			return "✅ Aplicado"
		return "⏳ Pendiente"
	estado_display.short_description = "Estado"

	def aplicar_turnos_mensuales(self, request, queryset):
		"""Aplicar los turnos mensuales seleccionados (crear cupos)."""
		from django.contrib import messages
		from django.db import transaction
		
		total_aplicados = 0
		total_cupos = 0
		ya_aplicados = 0
		
		for turno_mens in queryset:
			if not turno_mens.aplicado:
				try:
					with transaction.atomic():
						cupos_count = turno_mens.aplicar()
						total_cupos += cupos_count
						total_aplicados += 1
				except Exception as e:
					messages.error(request, f"Error al aplicar {turno_mens.agenda.name}: {str(e)}")
			else:
				ya_aplicados += 1
		
		if total_aplicados > 0:
			msg = f"✓ {total_aplicados} configuración(es) aplicada(s). {total_cupos} cupos creados (lunes-viernes)."
			messages.success(request, msg)
		
		if ya_aplicados > 0:
			messages.warning(request, f"⚠ {ya_aplicados} registro(s) ya estaban aplicados.")

	aplicar_turnos_mensuales.short_description = "Aplicar turnos mensuales seleccionados"
