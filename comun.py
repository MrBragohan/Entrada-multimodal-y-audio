"""Utilidades compartidas por todas las partes del taller multimodal.

Variables de entorno (archivo .env, NUNCA en el código):
    GROQ_API_KEY      obligatoria
    VISION_MODEL      modelo con visión           (por defecto qwen/qwen3.8-27b)
    STT_MODEL         modelo de voz a texto       (por defecto whisper-large-v3-turbo)
    TEXT_MODEL        modelo que responde al audio (por defecto qwen/qwen3.8-27b)
    REASONING_EFFORT  esfuerzo de razonamiento    (por defecto low; vacío = no enviarlo)
"""
import base64
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import groq
from dotenv import load_dotenv

load_dotenv()  # busca el .env en esta carpeta o en las carpetas superiores del repositorio

BASE = Path(__file__).parent
CARPETA_IMAGENES = BASE / "imagenes"
CARPETA_AUDIOS = BASE / "audios"
CARPETA_RESULTADOS = BASE / "resultados"

MODELO_VISION = os.getenv("VISION_MODEL", "qwen/qwen3.8-27b")
MODELO_STT = os.getenv("STT_MODEL", "whisper-large-v3-turbo")
MODELO_TEXTO = os.getenv("TEXT_MODEL", "qwen/qwen3.8-27b")
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "low")

# Límites documentados por Groq (validar si se cambia de modelo o proveedor)
MAX_IMAGENES = 3
MAX_MB_SOLICITUD = 20
MAX_MB_AUDIO = 25
MIN_SEGUNDOS_COBRADOS = 10

EXT_IMAGEN = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".webp": "image/webp", ".gif": "image/gif"}
EXT_AUDIO = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac", ".mp4", ".mpeg", ".mpga"}

# Rol del asistente: el Tutor Académico del proyecto (dominio: Creación de Aplicaciones con IA)
SISTEMA_TUTOR = (
    "Eres un Tutor Académico especializado en Creación de Aplicaciones con IA, dirigido a "
    "estudiantes de Ingeniería de Sistemas. Responde en español, de forma clara, breve y precisa."
)


# ---------------------------------------------------------------------------
# Cliente y llamadas
# ---------------------------------------------------------------------------
def cliente():
    """Cliente de Groq. Si falta la clave, termina con un mensaje claro (sin traceback)."""
    if not os.getenv("GROQ_API_KEY"):
        sys.exit("Falta GROQ_API_KEY. Créala en https://console.groq.com y ponla en el archivo "
                 ".env (copia .env.example como .env).")
    return groq.Groq()


def limpiar_respuesta(texto):
    """Quita bloques <think>...</think> que algunos modelos de razonamiento incluyen."""
    return re.sub(r"<think>.*?</think>", "", texto or "", flags=re.DOTALL).strip()


def llamar_chat(mensajes, modelo, max_tokens=4096, temperatura=0, json_mode=False,
                reintentar=True):
    """Llama al chat de Groq con reintentos ante fallos transitorios (429, 5xx, red).

    Los errores 400 (solicitud inválida) NO se reintentan: se propagan para poder estudiarlos
    (parte 4 del taller). Con `reintentar=False` tampoco se reintentan los fallos transitorios.
    Solo hay dos reintentos "inteligentes": si el modelo rechaza `reasoning_effort` o
    `response_format`, se repite la llamada sin ese parámetro.
    """
    cli = cliente()
    extra = {}
    if REASONING_EFFORT and any(k in modelo for k in ("qwen", "gpt-oss")):
        extra["reasoning_effort"] = REASONING_EFFORT
    if json_mode:
        extra["response_format"] = {"type": "json_object"}

    esperas = [3, 8, 20]
    intento = 0
    while True:
        try:
            r = cli.chat.completions.create(
                model=modelo, messages=mensajes, temperature=temperatura,
                max_completion_tokens=max_tokens, **extra,
            )
            return limpiar_respuesta(r.choices[0].message.content)
        except groq.BadRequestError as e:
            msg = str(e).lower()
            if "reasoning_effort" in extra and "reasoning" in msg:
                extra.pop("reasoning_effort")
                continue
            if "response_format" in extra and ("response_format" in msg or "json" in msg):
                extra.pop("response_format")
                continue
            raise
        except (groq.RateLimitError, groq.APIConnectionError, groq.InternalServerError):
            if not reintentar or intento >= len(esperas):
                raise
            print(f"   (servicio ocupado o límite de tasa; reintentando en {esperas[intento]} s...)")
            time.sleep(esperas[intento])
            intento += 1


# ---------------------------------------------------------------------------
# Imágenes
# ---------------------------------------------------------------------------
def listar_imagenes():
    return sorted(p for p in CARPETA_IMAGENES.iterdir() if p.suffix.lower() in EXT_IMAGEN)


def resolver_imagen(nombre_o_ruta):
    """Acepta un nombre de archivo (dentro de imagenes/) o una ruta."""
    p = Path(nombre_o_ruta)
    if p.exists():
        return p
    p = CARPETA_IMAGENES / nombre_o_ruta
    if p.exists():
        return p
    sys.exit(f"No encuentro la imagen '{nombre_o_ruta}' (ni como ruta ni en {CARPETA_IMAGENES}).")


def elegir_imagen(indice=None):
    """Lista las imágenes y devuelve una (por número, o preguntando si no se indica)."""
    imagenes = listar_imagenes()
    if not imagenes:
        sys.exit(f"No hay imágenes en {CARPETA_IMAGENES}. Copia allí tus .png/.jpg.")
    for i, img in enumerate(imagenes, 1):
        print(f"  {i}. {img.name}")
    if indice is None:
        indice = int(input("Número de la imagen: "))
    return imagenes[indice - 1]


def bloque_imagen_bytes(datos, mime):
    """Bloque de imagen en base64 para el mensaje (formato de la API de Groq)."""
    b64 = base64.b64encode(datos).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


def bloque_imagen(ruta):
    ruta = Path(ruta)
    mime = EXT_IMAGEN.get(ruta.suffix.lower())
    if mime is None:
        sys.exit(f"Formato no soportado: {ruta.suffix}. Usa {sorted(EXT_IMAGEN)}.")
    return bloque_imagen_bytes(ruta.read_bytes(), mime)


def mensaje_usuario(texto, rutas_imagenes=()):
    """Mensaje de usuario con un bloque de texto y N bloques de imagen."""
    contenido = [{"type": "text", "text": texto}]
    contenido += [bloque_imagen(r) for r in rutas_imagenes]
    return {"role": "user", "content": contenido}


def validar_solicitud_imagenes(rutas):
    """Comprueba los límites documentados ANTES de gastar una llamada. Devuelve [] si todo bien."""
    problemas = []
    if len(rutas) > MAX_IMAGENES:
        problemas.append(f"{len(rutas)} imágenes: el máximo es {MAX_IMAGENES} por solicitud.")
    # El base64 ocupa ~33 % más que el archivo original
    total_mb = sum(Path(r).stat().st_size for r in rutas) * 4 / 3 / 1024 / 1024
    if total_mb > MAX_MB_SOLICITUD:
        problemas.append(f"≈{total_mb:.1f} MB en base64: el máximo es {MAX_MB_SOLICITUD} MB.")
    return problemas


# ---------------------------------------------------------------------------
# Resultados (informes en Markdown para la entrega)
# ---------------------------------------------------------------------------
def guardar_texto(nombre, contenido):
    CARPETA_RESULTADOS.mkdir(exist_ok=True)
    ruta = CARPETA_RESULTADOS / nombre
    ruta.write_text(contenido, encoding="utf-8")
    print(f"\n[guardado] {ruta.relative_to(BASE.parent)}")
    return ruta


def guardar_json(nombre, datos):
    return guardar_texto(nombre, json.dumps(datos, ensure_ascii=False, indent=2))


def sello():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def describir_error_api(e):
    """Resume una excepción de la API: tipo, código HTTP y mensaje original del servidor."""
    return {
        "tipo": type(e).__name__,
        "codigo_http": getattr(e, "status_code", None),
        "mensaje": str(getattr(e, "message", None) or e),
        "cuerpo": getattr(e, "body", None),
    }


def salir_por_error_api(e):
    """Termina el programa mostrando el error de la API de forma legible (sin traceback)."""
    d = describir_error_api(e)
    sys.exit(f"\nError de la API ({d['tipo']}, HTTP {d['codigo_http']}):\n  {d['mensaje']}\n"
             "Revisa la clave, el nombre del modelo en .env (VISION_MODEL / STT_MODEL / "
             "TEXT_MODEL) y los límites del README.")
