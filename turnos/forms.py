from django import forms
from .models import Turno, Cupo, Agenda

class TurnoForm(forms.ModelForm):
    agenda = forms.ModelChoiceField(queryset=Agenda.objects.all(), required=True)

    class Meta:
        model = Turno
        fields = ['agenda','nombre','dni','determinaciones','fecha']
        widgets = {
            'fecha': forms.DateInput(attrs={'type':'date'})
        }


class CupoForm(forms.ModelForm):
    class Meta:
        model = Cupo
        fields = ['agenda','fecha', 'cantidad_total']
        widgets = {
            'fecha': forms.DateInput(attrs={'type':'date'})
        }
