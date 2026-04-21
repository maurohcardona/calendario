from django import forms
from django.core.exceptions import ValidationError
from .models import Turno, Cupo, Agenda, Feriados
from pacientes.models import Paciente
from datetime import date


class TurnoForm(forms.ModelForm):
    """Formulario para crear y editar turnos médicos.

    Incluye campos del paciente para facilitar la creación/actualización.
    """

    # Campos del paciente
    dni = forms.CharField(
        required=True,
        max_length=15,
        label="DNI",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ingrese DNI del paciente"}
        ),
        help_text="Documento de identidad del paciente",
    )
    nombre = forms.CharField(
        required=True,
        max_length=30,
        label="Nombre",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nombre"}
        ),
    )
    apellido = forms.CharField(
        required=True,
        max_length=30,
        label="Apellido",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Apellido"}
        ),
    )
    fecha_nacimiento = forms.DateField(
        required=True,
        label="Fecha de Nacimiento",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        help_text="Fecha de nacimiento del paciente",
    )
    sexo = forms.ChoiceField(
        choices=Paciente.SEXO_CHOICES,
        required=True,
        label="Sexo",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    telefono = forms.CharField(
        required=False,
        max_length=20,
        label="Teléfono",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Teléfono de contacto"}
        ),
        help_text="Número de teléfono del paciente",
    )
    email = forms.EmailField(
        required=False,
        max_length=100,
        label="Email",
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "correo@ejemplo.com"}
        ),
        help_text="Correo electrónico del paciente",
    )
    medico = forms.CharField(
        required=False,
        max_length=200,
        label="Médico Solicitante",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nombre del médico"}
        ),
        help_text="Médico que solicita los estudios",
    )
    institucion = forms.CharField(
        required=False,
        max_length=200,
        label="Institución",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Institución de origen",
                "autocomplete": "off",
            }
        ),
        help_text="Institución de origen de la orden médica",
    )
    nota_interna = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-control",
                "placeholder": "Notas internas sobre el turno",
            }
        ),
        label="Nota Interna",
        help_text="Observaciones internas (no visibles para el paciente)",
    )
    observaciones_paciente = forms.CharField(
        required=False,
        max_length=255,
        label="Observaciones del Paciente",
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "class": "form-control",
                "placeholder": "Observaciones sobre el paciente",
            }
        ),
        help_text="Notas sobre condiciones o particularidades del paciente",
    )

    class Meta:
        model = Turno
        fields = ["agenda", "determinaciones", "fecha"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "determinaciones": forms.HiddenInput(),
            "agenda": forms.Select(attrs={"class": "form-control"}),
        }
        labels = {
            "agenda": "Agenda/Servicio",
            "determinaciones": "Determinaciones",
            "fecha": "Fecha del Turno",
        }
        help_texts = {
            "agenda": "Seleccione la agenda o servicio para el turno",
            "fecha": "Fecha en la que se asignará el turno",
            "determinaciones": "Lista de estudios o análisis solicitados",
        }

    def clean_fecha(self):
        """Valida que la fecha del turno no sea un feriado ni una fecha pasada."""
        fecha = self.cleaned_data.get("fecha")

        if not fecha:
            raise ValidationError("Debe seleccionar una fecha para el turno.")

        # Validar que no sea una fecha pasada
        if fecha < date.today():
            raise ValidationError("No se pueden crear turnos en fechas pasadas.")

        # Validar que no sea un feriado
        if Feriados.objects.filter(fecha=fecha).exists():
            feriado = Feriados.objects.get(fecha=fecha)
            raise ValidationError(
                f"No se pueden asignar turnos en feriados: {feriado.descripcion}"
            )

        return fecha

    def clean_dni(self):
        """Valida y normaliza el DNI."""
        dni = self.cleaned_data.get("dni", "").strip()

        if not dni:
            raise ValidationError("El DNI es obligatorio.")

        # Remover espacios y caracteres especiales
        dni = "".join(filter(str.isalnum, dni))

        if len(dni) < 6:
            raise ValidationError("El DNI debe tener al menos 6 caracteres.")

        return dni

    def clean_email(self):
        """Normaliza el email si está presente."""
        email = self.cleaned_data.get("email", "").strip().lower()
        return email if email else ""

    def clean_telefono(self):
        """Normaliza el teléfono."""
        telefono = self.cleaned_data.get("telefono", "").strip()
        return telefono if telefono else ""


class CupoForm(forms.ModelForm):
    """Formulario para gestionar cupos de agendas por fecha."""

    class Meta:
        model = Cupo
        fields = ["agenda", "fecha", "cantidad_total"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "agenda": forms.Select(attrs={"class": "form-control"}),
            "cantidad_total": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "1",
                    "placeholder": "Cantidad de turnos disponibles",
                }
            ),
        }
        labels = {
            "agenda": "Agenda/Servicio",
            "fecha": "Fecha",
            "cantidad_total": "Cantidad Total de Cupos",
        }
        help_texts = {
            "agenda": "Seleccione la agenda para asignar cupos",
            "fecha": "Fecha para la cual se asignan los cupos",
            "cantidad_total": "Número total de turnos disponibles para esta fecha",
        }

    def clean_cantidad_total(self):
        """Valida que la cantidad sea positiva."""
        cantidad = self.cleaned_data.get("cantidad_total")

        if cantidad is not None and cantidad < 1:
            raise ValidationError("La cantidad de cupos debe ser al menos 1.")

        return cantidad

    def clean_fecha(self):
        """Valida que la fecha no sea pasada."""
        fecha = self.cleaned_data.get("fecha")

        if not fecha:
            raise ValidationError("Debe seleccionar una fecha.")

        if fecha < date.today():
            raise ValidationError("No se pueden crear cupos en fechas pasadas.")

        return fecha

    def clean(self):
        """Validación global del formulario."""
        cleaned_data = super().clean()
        agenda = cleaned_data.get("agenda")
        fecha = cleaned_data.get("fecha")

        # Validar que no exista ya un cupo para esta agenda y fecha
        if agenda and fecha:
            if self.instance.pk:
                # Si estamos editando, excluir el registro actual
                existe = (
                    Cupo.objects.filter(agenda=agenda, fecha=fecha)
                    .exclude(pk=self.instance.pk)
                    .exists()
                )
            else:
                existe = Cupo.objects.filter(agenda=agenda, fecha=fecha).exists()

            if existe:
                raise ValidationError(
                    f"Ya existe un cupo para {agenda.name} en la fecha {fecha.strftime('%d/%m/%Y')}."
                )

        return cleaned_data
