from django import forms
from .models import Turno

class TurnoForm(forms.ModelForm):
    class Meta:
        model = Turno
        fields = ['nombre','dni','determinaciones','fecha']
        widgets = {
            'fecha': forms.DateInput(attrs={'type':'date'})
        }
