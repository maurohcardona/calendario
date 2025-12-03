from django import forms
from .models import Turno, Cupo

class TurnoForm(forms.ModelForm):
    class Meta:
        model = Turno
        fields = ['nombre','dni','determinaciones','fecha']
        widgets = {
            'fecha': forms.DateInput(attrs={'type':'date'})
        }


class CupoForm(forms.ModelForm):
    class Meta:
        model = Cupo
        fields = ['fecha', 'cantidad_total']
        widgets = {
            'fecha': forms.DateInput(attrs={'type':'date'})
        }
