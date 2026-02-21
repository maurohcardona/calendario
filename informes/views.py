from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.urls import reverse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Informes
from .services import InformesService


def _obtener_pdfs(carpeta: Path):
	if not carpeta.exists() or not carpeta.is_dir():
		return []

	return sorted(
		[archivo.name for archivo in carpeta.iterdir() if archivo.is_file() and archivo.suffix.lower() == ".pdf"],
		reverse=True,
	)


def _obtener_pdf_por_estado(estado: str, nombre_archivo: str) -> Path:
	if estado not in {"enviados", "pendientes"}:
		raise Http404("Estado inválido")

	base_informes = Path(settings.BASE_DIR) / "informes"
	carpeta = (base_informes / estado).resolve()
	archivo = (carpeta / nombre_archivo).resolve()

	try:
		archivo.relative_to(carpeta)
	except ValueError as exc:
		raise Http404("Archivo inválido") from exc

	if not archivo.exists() or not archivo.is_file() or archivo.suffix.lower() != ".pdf":
		raise Http404("Archivo no encontrado")

	return archivo


def _query_desde_request(request):
	q = request.POST.get("q", "").strip()
	page_enviados = request.POST.get("page_enviados", "1")
	page_pendientes = request.POST.get("page_pendientes", "1")

	query = urlencode(
		{
			"q": q,
			"page_enviados": page_enviados,
			"page_pendientes": page_pendientes,
		}
	)
	return f"?{query}"


def _redirect_listado(request):
	return redirect(f"{reverse('informes:listado')}{_query_desde_request(request)}")


@login_required
def listado_informes(request):
	base_informes = Path(settings.BASE_DIR) / "informes"
	carpeta_enviados = base_informes / "enviados"
	carpeta_pendientes = base_informes / "pendientes"
	termino_busqueda = request.GET.get("q", "").strip()
	page_enviados = request.GET.get("page_enviados", "1")
	page_pendientes = request.GET.get("page_pendientes", "1")
	pdfs_por_pagina = 20

	pdfs_enviados = _obtener_pdfs(carpeta_enviados)
	pdfs_pendientes = _obtener_pdfs(carpeta_pendientes)

	if termino_busqueda:
		termino_normalizado = termino_busqueda.lower()
		pdfs_enviados = [archivo for archivo in pdfs_enviados if termino_normalizado in archivo.lower()]
		pdfs_pendientes = [archivo for archivo in pdfs_pendientes if termino_normalizado in archivo.lower()]

	total_enviados = len(pdfs_enviados)
	total_pendientes = len(pdfs_pendientes)

	pdfs_enviados_page = Paginator(pdfs_enviados, pdfs_por_pagina).get_page(page_enviados)
	pdfs_pendientes_page = Paginator(pdfs_pendientes, pdfs_por_pagina).get_page(page_pendientes)

	context = {
		"pdfs_enviados": pdfs_enviados_page,
		"pdfs_pendientes": pdfs_pendientes_page,
		"total_enviados": total_enviados,
		"total_pendientes": total_pendientes,
		"termino_busqueda": termino_busqueda,
		"page_enviados_actual": pdfs_enviados_page.number,
		"page_pendientes_actual": pdfs_pendientes_page.number,
	}
	return render(request, "informes/listado_pdfs.html", context)


@login_required
def ver_pdf(request, estado, nombre_archivo):
	archivo = _obtener_pdf_por_estado(estado, nombre_archivo)

	return FileResponse(open(archivo, "rb"), content_type="application/pdf")


@login_required
@require_POST
def enviar_informe(request, estado, nombre_archivo):
	archivo = _obtener_pdf_por_estado(estado, nombre_archivo)
	service = InformesService()

	if estado == "pendientes":
		resultado = service.procesar_archivo(archivo)
		if resultado.get("exito"):
			messages.success(request, f"Informe enviado: {nombre_archivo}")
		else:
			messages.error(request, f"No se pudo enviar {nombre_archivo}: {resultado.get('error', 'Error desconocido')}")
		return _redirect_listado(request)

	datos = service.parsear_nombre_archivo(nombre_archivo)
	if not datos:
		messages.error(request, f"Formato inválido para reenviar: {nombre_archivo}")
		return _redirect_listado(request)

	paciente = service.buscar_paciente(datos["iden"])
	if not paciente:
		messages.error(request, f"No se encontró el paciente {datos['iden']} para reenviar {nombre_archivo}")
		return _redirect_listado(request)

	if not paciente.email:
		messages.error(request, f"El paciente {datos['iden']} no tiene email para reenviar {nombre_archivo}")
		return _redirect_listado(request)

	informe, _ = Informes.objects.get_or_create(
		paciente=paciente,
		numero_orden=datos["orden"],
		numero_protocolo=datos["protocolo"],
		defaults={
			"nombre_archivo": nombre_archivo,
			"email_destino": paciente.email,
			"estado": "PENDIENTE",
		},
	)

	informe.nombre_archivo = nombre_archivo
	informe.email_destino = paciente.email
	informe.intentos_envio += 1

	if service.enviar_email(informe, archivo):
		informe.estado = "ENVIADO"
		informe.fecha_envio = timezone.now()
		informe.mensaje_error = ""
		informe.save()
		messages.success(request, f"Informe reenviado: {nombre_archivo}")
	else:
		informe.estado = "ERROR"
		informe.save()
		messages.error(request, f"No se pudo reenviar {nombre_archivo}: {informe.mensaje_error or 'Error desconocido'}")

	return _redirect_listado(request)
