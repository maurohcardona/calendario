import datetime

from django import forms
from determinaciones.models import Determinacion, DeterminacionCompleja
from pacientes.models import Paciente
from .models import OrdenLaboratorio, Servicio


class PacienteInlineForm(forms.ModelForm):
    """Formulario inline para crear o identificar un paciente al registrar una orden."""

    class Meta:
        model = Paciente
        fields = ["tipo_iden", "iden", "apellido", "nombre", "fecha_nacimiento", "sexo", "telefono", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.required = False
            widget = field.widget
            css = widget.attrs.get("class", "")
            if "form-select" not in css and "form-control" not in css:
                if hasattr(widget, "choices"):
                    widget.attrs["class"] = (css + " form-select").strip()
                else:
                    widget.attrs["class"] = (css + " form-control").strip()
            if name in ("nombre", "apellido"):
                widget.attrs["style"] = "text-transform: uppercase;"
                widget.attrs["oninput"] = "this.value = this.value.toUpperCase();"
        # El campo iden tiene id estándar que usará el JS del template
        self.fields["iden"].widget.attrs["id"] = "id_iden_paciente"

    def clean(self):
        """Validar reglas para tipo NEO: edad máxima 90 días, iden puede ser vacío."""
        from turnos.services.turno_service import validar_edad_neo

        cleaned_data = super().clean()
        tipo_iden = cleaned_data.get("tipo_iden", "DNI")
        fecha_nacimiento = cleaned_data.get("fecha_nacimiento")

        if tipo_iden == "NEO":
            # Para NEO el iden se genera server-side; no validar campo iden
            if fecha_nacimiento:
                es_valido, mensaje = validar_edad_neo(fecha_nacimiento)
                if not es_valido:
                    raise forms.ValidationError(mensaje)
            else:
                raise forms.ValidationError(
                    "La fecha de nacimiento es obligatoria para el tipo de identificación NEO."
                )

        return cleaned_data


class OrdenForm(forms.ModelForm):
    determinaciones = forms.ModelMultipleChoiceField(
        queryset=Determinacion.objects.filter(activa=True, visible=True).order_by("nombre"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    determinaciones_complejas = forms.ModelMultipleChoiceField(
        queryset=DeterminacionCompleja.objects.filter(activa=True, visible=True).order_by("nombre"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["determinaciones"].label_from_instance = lambda obj: obj.nombre
        self.fields["determinaciones_complejas"].label_from_instance = lambda obj: obj.nombre

    class Meta:
        model = OrdenLaboratorio
        fields = ["tipo_origen", "servicio", "sala", "observaciones", "determinaciones", "determinaciones_complejas"]

    def clean(self):
        cleaned_data = super().clean()
        dets = cleaned_data.get("determinaciones")
        dets_c = cleaned_data.get("determinaciones_complejas")
        if not dets and not dets_c:
            raise forms.ValidationError("Seleccioná al menos una determinación.")
        return cleaned_data


class IngresarOrdenForm(forms.ModelForm):
    class Meta:
        model = OrdenLaboratorio
        fields = ["observaciones_lab"]
        labels = {
            "observaciones_lab": "Observaciones",
        }


class VincularTurnoForm(forms.ModelForm):
    class Meta:
        model = OrdenLaboratorio
        fields = ["turno"]
        labels = {"turno": "Turno"}


class CancelarOrdenForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo de cancelación",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )


class OrdenProgramadaForm(forms.ModelForm):
    """Formulario exclusivo para el origen Órdenes Programadas."""

    fecha_programada = forms.DateField(
        label="Fecha programada",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        required=True,
    )
    determinaciones = forms.ModelMultipleChoiceField(
        queryset=Determinacion.objects.filter(activa=True, visible=True).order_by("nombre"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    determinaciones_complejas = forms.ModelMultipleChoiceField(
        queryset=DeterminacionCompleja.objects.filter(activa=True, visible=True).order_by("nombre"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Excluir servicios ambulatorios
        self.fields["servicio"].queryset = Servicio.objects.exclude(
            origen="AMBULATORIO"
        ).filter(activo=True).order_by("origen", "nombre")
        self.fields["servicio"].required = True
        self.fields["servicio"].empty_label = "---------"
        self.fields["determinaciones"].label_from_instance = lambda obj: obj.nombre
        self.fields["determinaciones_complejas"].label_from_instance = lambda obj: obj.nombre

    class Meta:
        model = OrdenLaboratorio
        fields = [
            "servicio",
            "sala",
            "fecha_programada",
            "observaciones",
            "determinaciones",
            "determinaciones_complejas",
        ]
        labels = {
            "sala": "Cama / Sala",
            "observaciones": "Diagnóstico y/u Observaciones",
        }
        widgets = {
            "sala": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Cama 12 - Sala C"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Diagnóstico, notas clínicas..."}),
        }

    def clean_fecha_programada(self):
        """Validar que la fecha no sea anterior a hoy."""
        fecha = self.cleaned_data.get("fecha_programada")
        if fecha and fecha < datetime.date.today():
            raise forms.ValidationError(
                "La fecha programada no puede ser anterior a hoy."
            )
        return fecha

    def clean(self):
        cleaned_data = super().clean()
        dets = cleaned_data.get("determinaciones")
        dets_c = cleaned_data.get("determinaciones_complejas")
        if not dets and not dets_c:
            raise forms.ValidationError("Seleccioná al menos una determinación.")
        return cleaned_data
