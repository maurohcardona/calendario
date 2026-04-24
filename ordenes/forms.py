from django import forms
from determinaciones.models import Determinacion, DeterminacionCompleja
from pacientes.models import Paciente
from .models import OrdenLaboratorio, Servicio


class PacienteInlineForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = ["iden", "apellido", "nombre", "fecha_nacimiento", "sexo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False


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
        fields = ["numero_orden_lab", "observaciones_lab"]
        labels = {
            "numero_orden_lab": "Número de orden (lab)",
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
