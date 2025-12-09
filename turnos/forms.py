from django import forms
from .models import Turno, Cupo, Agenda

class TurnoForm(forms.ModelForm):
    agenda = forms.ModelChoiceField(queryset=Agenda.objects.all(), required=True)
    fecha_nacimiento = forms.DateField(
        required=True, 
        label="Fecha de Nacimiento",
        widget=forms.DateInput(attrs={'type':'date'})
    )
    sexo = forms.ChoiceField(
        choices=[('Desconocido', 'Desconocido'), ('Generico', 'Genérico'), ('Hombre', 'Hombre'), ('Mujer', 'Mujer')],
        required=True,
        label="Sexo"
    )
    observaciones_paciente = forms.CharField(
        required=False, 
        widget=forms.Textarea(attrs={'rows': 3}),
        label="Observaciones del Paciente"
    )
    telefono = forms.CharField(
        required=False,
        max_length=50,
        label="Teléfono"
    )
    email = forms.EmailField(
        required=False,
        max_length=100,
        label="Email"
    )
    medico = forms.CharField(
        required=False,
        max_length=200,
        label="Médico"
    )

    class Meta:
        model = Turno
        fields = ['agenda','apellido','nombre','dni','determinaciones','fecha']
        widgets = {
            'fecha': forms.DateInput(attrs={'type':'date'}),
            'determinaciones': forms.HiddenInput()
        }


class CupoForm(forms.ModelForm):
    class Meta:
        model = Cupo
        fields = ['agenda','fecha', 'cantidad_total']
        widgets = {
            'fecha': forms.DateInput(attrs={'type':'date'})
        }
