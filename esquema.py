"""Esquema de extracción estructurada (Parte 1.2) y su comparación con la lectura humana.

Dominio del proyecto: Tutor Académico de Creación de Aplicaciones con IA. Las imágenes del
dominio son figuras, tablas, diapositivas o capturas técnicas (arquitecturas RAG, tablas de
métricas, gráficos de resultados, código de prompts...).

Si cambias de dominio o de campos, edita SOLO este archivo: el modelo `FichaFigura`, la
descripción de cada campo (`CAMPOS`) y la forma de compararlos (`TIPO_CAMPO`).
"""
import difflib
import json
import re
import unicodedata
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

TIPOS = ["diagrama", "tabla", "grafico", "captura_de_codigo", "captura_de_interfaz",
         "texto_o_diapositiva", "otro"]


class FichaFigura(BaseModel):
    """Ficha de una figura técnica. 6 campos; `extra='forbid'` rechaza campos inventados."""
    model_config = ConfigDict(extra="forbid")

    tipo_contenido: Literal["diagrama", "tabla", "grafico", "captura_de_codigo",
                            "captura_de_interfaz", "texto_o_diapositiva", "otro"]
    titulo: Optional[str]
    idioma: Literal["es", "en", "otro"]
    numero_de_elementos: int = Field(ge=0)
    terminos_tecnicos: List[str] = Field(max_length=8)
    contiene_numeros: bool


# Instrucción de cada campo (se inserta en el prompt)
CAMPOS = {
    "tipo_contenido": f"uno de {TIPOS}",
    "titulo": "título o leyenda visible de la figura, copiado tal cual; null si no hay ninguno",
    "idioma": "idioma del texto de la imagen: 'es', 'en' u 'otro'",
    "numero_de_elementos": ("entero: cajas o nodos de un diagrama, FILAS DE DATOS de una tabla "
                            "(sin contar el encabezado), barras o series de un gráfico, ítems de "
                            "una lista o diapositiva; 0 si es una captura de código"),
    "terminos_tecnicos": "lista de hasta 5 términos técnicos escritos en la imagen, tal cual aparecen",
    "contiene_numeros": "true si la imagen muestra valores numéricos (métricas, porcentajes, "
                        "cantidades); false si no",
}

# Cómo se compara cada campo con el valor real:
#   exacto -> debe coincidir (puntaje 0 o 1)      texto -> parecido >= 0.8 (puntaje 0 o 1)
#   lista  -> puntaje F1 entre las dos listas
TIPO_CAMPO = {
    "tipo_contenido": "exacto",
    "titulo": "texto",
    "idioma": "exacto",
    "numero_de_elementos": "exacto",
    "terminos_tecnicos": "lista",
    "contiene_numeros": "exacto",
}
UMBRAL_ACIERTO = 0.8  # un campo cuenta como "acierto" si su puntaje es >= 0.8


def construir_prompt():
    reglas = "\n".join(f"- {campo}: {desc}" for campo, desc in CAMPOS.items())
    return (
        "Analiza la imagen y devuelve ÚNICAMENTE un objeto JSON válido, sin texto adicional ni "
        "bloques de código markdown, con EXACTAMENTE estos campos (no agregues otros):\n"
        f"{reglas}\n"
        "Lee los valores directamente de lo que se ve en la imagen; no inventes datos."
    )


# ---------------------------------------------------------------------------
# Parseo y validación (si algo falla se INFORMA, no se lanza una excepción)
# ---------------------------------------------------------------------------
def extraer_json(texto):
    """Obtiene el primer objeto JSON de un texto (tolera ```json ... ``` y texto alrededor)."""
    texto = re.sub(r"```(?:json)?", "", texto or "").strip()
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fin <= inicio:
        raise ValueError("la respuesta no contiene un objeto JSON")
    return json.loads(texto[inicio:fin + 1])


def validar(texto):
    """Devuelve (ficha_dict | None, [errores]). Nunca lanza excepciones por datos malos."""
    try:
        datos = extraer_json(texto)
    except (ValueError, json.JSONDecodeError) as e:
        return None, [f"JSON inválido: {e}"]
    try:
        return FichaFigura(**datos).model_dump(), []
    except ValidationError as e:
        errores = [f"{'.'.join(str(p) for p in err['loc']) or '(objeto)'}: {err['msg']}"
                   for err in e.errors()]
        return None, errores
    except TypeError as e:
        return None, [f"estructura inesperada: {e}"]


# ---------------------------------------------------------------------------
# Comparación campo por campo con la lectura humana (ground truth)
# ---------------------------------------------------------------------------
def normalizar(valor):
    s = unicodedata.normalize("NFD", str(valor).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _f1_listas(extraida, real):
    if not extraida and not real:
        return 1.0
    if not extraida or not real:
        return 0.0
    pred = [normalizar(x) for x in extraida]
    ref = [normalizar(x) for x in real]

    def coincide(a, b):
        return a == b or a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() >= 0.85

    aciertos_ref = sum(any(coincide(p, r) for p in pred) for r in ref)
    aciertos_pred = sum(any(coincide(p, r) for r in ref) for p in pred)
    recall, precision = aciertos_ref / len(ref), aciertos_pred / len(pred)
    return 0.0 if recall + precision == 0 else 2 * precision * recall / (precision + recall)


def puntuar_campo(campo, extraido, real):
    tipo = TIPO_CAMPO.get(campo, "exacto")
    if tipo == "lista":
        return round(_f1_listas(extraido or [], real or []), 3)
    if tipo == "texto":
        if extraido is None or real is None:
            return 1.0 if extraido == real else 0.0
        parecido = difflib.SequenceMatcher(None, normalizar(extraido), normalizar(real)).ratio()
        return 1.0 if parecido >= 0.8 else 0.0
    return 1.0 if extraido == real else 0.0


def comparar(extraido, real):
    """Lista de filas {campo, esperado, extraido, puntaje, acierto} para los campos del esquema."""
    filas = []
    for campo in FichaFigura.model_fields:
        p = puntuar_campo(campo, extraido.get(campo), real.get(campo))
        filas.append({"campo": campo, "esperado": real.get(campo), "extraido": extraido.get(campo),
                      "puntaje": p, "acierto": p >= UMBRAL_ACIERTO})
    return filas
