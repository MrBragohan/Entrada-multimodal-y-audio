"""Parte 2 — Audio: transcripción con Whisper y respuesta del modelo.

Procesa todos los audios de audios/ (wav, mp3, m4a, ogg, webm...):
  1. Valida el archivo (formato y tamaño ≤ 25 MB en el plan gratuito).
  2. Transcribe con Whisper (STT_MODEL) en español.
  3. Pasa la transcripción al modelo de texto para que responda como Tutor Académico.
  4. (Opcional) Si existe audios/referencias.json con lo que dijiste, calcula el WER
     (Word Error Rate = errores de palabras / palabras reales; 0 % es perfecto).

Uso:
    python 5_audio_transcripcion.py                         # todos los audios de audios/
    python 5_audio_transcripcion.py --archivo audio_01.wav  # uno solo
    python 5_audio_transcripcion.py --comparar-vocabulario  # transcribe con y sin pista de vocabulario
    python 5_audio_transcripcion.py --sin-respuesta         # solo transcribir

Formato de audios/referencias.json (opcional; grabar_audio.py lo va llenando):
    {"audio_01.wav": {"texto": "qué es el chunking en un sistema rag", "hablante": "Ana", "ruido": false}}
"""
import argparse
import json
import os
import re
import time
import unicodedata
import wave
from pathlib import Path

import groq

import comun

# Pista de vocabulario para Whisper (parámetro `prompt`): ayuda con términos técnicos poco comunes
VOCABULARIO = os.getenv(
    "VOCABULARIO_AUDIO",
    "RAG, embeddings, chunking, ChromaDB, Ragas, faithfulness, context precision, context recall, "
    "prompt engineering, few-shot, system prompt, function calling, fine-tuning, LLM, top_k, Groq, "
    "Whisper, Streamlit.",
)
RUTA_REFERENCIAS = comun.CARPETA_AUDIOS / "referencias.json"


# ---------------------------------------------------------------------------
# Utilidades de audio
# ---------------------------------------------------------------------------
def listar_audios():
    if not comun.CARPETA_AUDIOS.exists():
        return []
    return sorted(p for p in comun.CARPETA_AUDIOS.iterdir() if p.suffix.lower() in comun.EXT_AUDIO)


def validar_audio(ruta):
    """Devuelve un mensaje de problema o None si el archivo cumple los límites."""
    if ruta.suffix.lower() not in comun.EXT_AUDIO:
        return f"formato {ruta.suffix} no soportado (usa {sorted(comun.EXT_AUDIO)})"
    mb = ruta.stat().st_size / 1024 / 1024
    if mb > comun.MAX_MB_AUDIO:
        return f"pesa {mb:.1f} MB y el máximo es {comun.MAX_MB_AUDIO} MB"
    return None


def duracion_local(ruta):
    """Duración en segundos de un WAV (para otros formatos se usa la que informa la API)."""
    if ruta.suffix.lower() != ".wav":
        return None
    try:
        with wave.open(str(ruta), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError):
        return None


def cargar_referencias():
    if not RUTA_REFERENCIAS.exists():
        return {}
    datos = json.loads(RUTA_REFERENCIAS.read_text(encoding="utf-8"))
    return {k: v for k, v in datos.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Calidad: WER
# ---------------------------------------------------------------------------
def _palabras(texto):
    t = unicodedata.normalize("NFC", texto.lower())
    return re.sub(r"[^\w\s]", " ", t).split()


def wer(referencia, hipotesis):
    """Word Error Rate = (sustituciones + eliminaciones + inserciones) / palabras de referencia."""
    r, h = _palabras(referencia), _palabras(hipotesis)
    if not r:
        return None
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        previo, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            actual = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, previo + (r[i - 1] != h[j - 1]))
            previo = actual
    return d[len(h)] / len(r)


# ---------------------------------------------------------------------------
# Whisper
# ---------------------------------------------------------------------------
def transcribir(ruta, prompt=None):
    """Transcribe un archivo. Devuelve (texto, duracion_en_segundos | None)."""
    cli = comun.cliente()
    kwargs = dict(file=(ruta.name, ruta.read_bytes()), model=comun.MODELO_STT, language="es",
                  temperature=0, response_format="verbose_json")
    if prompt:
        kwargs["prompt"] = prompt

    esperas, intento = [3, 8, 20], 0
    while True:
        try:
            r = cli.audio.transcriptions.create(**kwargs)
            break
        except groq.BadRequestError as e:
            if "response_format" in kwargs and "response_format" in str(e).lower():
                kwargs.pop("response_format")  # el modelo no soporta verbose_json: reintentar
                continue
            raise
        except (groq.RateLimitError, groq.APIConnectionError, groq.InternalServerError):
            if intento >= len(esperas):
                raise
            print(f"   (servicio ocupado; reintentando en {esperas[intento]} s...)")
            time.sleep(esperas[intento])
            intento += 1

    texto = getattr(r, "text", None) or (r.get("text") if isinstance(r, dict) else "") or ""
    dump = r.model_dump() if hasattr(r, "model_dump") else (r if isinstance(r, dict) else {})
    duracion = getattr(r, "duration", None) or dump.get("duration")
    return texto.strip(), duracion


def responder(transcripcion):
    return comun.llamar_chat(
        [{"role": "system", "content": comun.SISTEMA_TUTOR},
         {"role": "user", "content": transcripcion}],
        comun.MODELO_TEXTO,
    )


def fmt_pct(x):
    return "—" if x is None else f"{100 * x:.1f} %"


# ---------------------------------------------------------------------------
def procesar(ruta, refs, args):
    ref = refs.get(ruta.name, {})
    print(f"\n{'=' * 78}\nAudio: {ruta.name}  |  hablante: {ref.get('hablante', '?')}  |  "
          f"ruido de fondo: {ref.get('ruido', '?')}\n{'=' * 78}")
    reg = {"audio": ruta.name, "hablante": ref.get("hablante"), "ruido": ref.get("ruido"),
           "referencia": ref.get("texto"), "error": None}

    problema = validar_audio(ruta)
    if problema:
        reg["error"] = f"no se envía: {problema}"
        print(f"✗ {reg['error']}")
        return reg

    try:
        texto, dur_api = transcribir(ruta, VOCABULARIO if args.vocabulario else None)
        reg["transcripcion"] = texto
        dur = duracion_local(ruta) or dur_api
        reg["duracion_s"] = round(dur, 1) if dur else None
        reg["segundos_facturados"] = max(dur, comun.MIN_SEGUNDOS_COBRADOS) if dur else None

        etiqueta = "con pista de vocabulario" if args.vocabulario else "sin pista de vocabulario"
        print(f"Duración: {reg['duracion_s']} s"
              + (f"  → se factura como {comun.MIN_SEGUNDOS_COBRADOS} s (mínimo por solicitud)"
                 if dur and dur < comun.MIN_SEGUNDOS_COBRADOS else ""))
        print(f"Transcripción ({etiqueta}):\n  {texto}")

        if args.comparar_vocabulario:
            texto2, _ = transcribir(ruta, None if args.vocabulario else VOCABULARIO)
            reg["transcripcion_alternativa"] = texto2
            et2 = "sin pista de vocabulario" if args.vocabulario else "con pista de vocabulario"
            print(f"Transcripción ({et2}):\n  {texto2}")

        if ref.get("texto"):
            reg["wer"] = wer(ref["texto"], texto)
            print(f"Texto real     :\n  {ref['texto']}\nWER: {fmt_pct(reg['wer'])}")
            if "transcripcion_alternativa" in reg:
                reg["wer_alternativa"] = wer(ref["texto"], reg["transcripcion_alternativa"])
                print(f"WER (alternativa): {fmt_pct(reg['wer_alternativa'])}")

        if not args.sin_respuesta:
            if not texto:
                print("(transcripción vacía: no se consulta al modelo; ¿el audio tiene voz?)")
            else:
                reg["respuesta"] = responder(texto)
                print(f"\nRespuesta del modelo ({comun.MODELO_TEXTO}):\n{reg['respuesta']}")
    except groq.APIError as e:
        d = comun.describir_error_api(e)
        reg["error"] = f"{d['tipo']} (HTTP {d['codigo_http']}): {d['mensaje']}"
        print(f"✗ Error de la API: {reg['error']}")
    return reg


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--archivo", help="un audio concreto (nombre dentro de audios/ o ruta)")
    p.add_argument("--vocabulario", action="store_true",
                   help="envía a Whisper una pista con el vocabulario técnico del dominio")
    p.add_argument("--comparar-vocabulario", action="store_true",
                   help="transcribe cada audio con y sin la pista de vocabulario")
    p.add_argument("--sin-respuesta", action="store_true", help="solo transcribir")
    args = p.parse_args()

    if args.archivo:
        ruta = comun.CARPETA_AUDIOS / args.archivo
        if not ruta.exists():
            ruta = Path(args.archivo)
        if not ruta.exists():
            raise SystemExit(f"No encuentro el audio '{args.archivo}'.")
        audios = [ruta]
    else:
        audios = listar_audios()
    if not audios:
        raise SystemExit(f"No hay audios en {comun.CARPETA_AUDIOS}. Grábalos con "
                         "'python grabar_audio.py' o copia tus archivos allí.")

    refs = cargar_referencias()
    print(f"Whisper: {comun.MODELO_STT} | Modelo de respuesta: {comun.MODELO_TEXTO} | "
          f"Audios: {len(audios)}")
    resultados = [procesar(a, refs, args) for a in audios]

    # ------------------------------------------------------------------ resumen
    ok = [r for r in resultados if not r["error"]]
    con_wer = [r for r in ok if r.get("wer") is not None]
    facturados = sum(r["segundos_facturados"] or 0 for r in ok)
    print(f"\n{'#' * 78}\nRESUMEN\n{'#' * 78}")
    print(f"Audios transcritos: {len(ok)}/{len(resultados)} | segundos facturados: {facturados:.0f} s")
    md_resumen = [f"- Audios transcritos: {len(ok)}/{len(resultados)}\n"
                  f"- Segundos facturados (mínimo {comun.MIN_SEGUNDOS_COBRADOS} s por solicitud): "
                  f"{facturados:.0f} s\n"]
    if con_wer:
        medio = sum(r["wer"] for r in con_wer) / len(con_wer)
        print(f"WER medio ({len(con_wer)} audios con referencia): {fmt_pct(medio)}")
        md_resumen.append(f"- **WER medio:** {fmt_pct(medio)} ({len(con_wer)} audios con referencia)\n")
        for etiqueta, clave in (("con ruido de fondo", True), ("sin ruido de fondo", False)):
            g = [r["wer"] for r in con_wer if r.get("ruido") is clave]
            if g:
                print(f"  WER {etiqueta}: {fmt_pct(sum(g) / len(g))} ({len(g)} audios)")
                md_resumen.append(f"- WER {etiqueta}: {fmt_pct(sum(g) / len(g))} ({len(g)} audios)\n")
        alt = [r for r in con_wer if r.get("wer_alternativa") is not None]
        if alt:
            m2 = sum(r["wer_alternativa"] for r in alt) / len(alt)
            print(f"  WER de la transcripción alternativa: {fmt_pct(m2)}")
            md_resumen.append(f"- WER de la transcripción alternativa: {fmt_pct(m2)}\n")
    else:
        print("Sin referencias: no se calcula el WER (opcional; ver audios/referencias.json).")

    md = [f"# Parte 2 — Audio y transcripción\n\n- Fecha: {comun.sello()}\n"
          f"- Whisper: `{comun.MODELO_STT}` | Respuesta: `{comun.MODELO_TEXTO}`\n", *md_resumen]
    for r in resultados:
        md.append(f"\n## {r['audio']}\n\n- Hablante: {r['hablante'] or '—'} | "
                  f"Ruido de fondo: {r['ruido'] if r['ruido'] is not None else '—'} | "
                  f"Duración: {r.get('duracion_s', '—')} s\n")
        if r["error"]:
            md.append(f"\n✗ {r['error']}\n")
            continue
        md.append(f"\n**Transcripción:** {r['transcripcion']}\n")
        if r.get("transcripcion_alternativa") is not None:
            md.append(f"\n**Transcripción alternativa:** {r['transcripcion_alternativa']}\n")
        if r.get("referencia"):
            md.append(f"\n**Texto real:** {r['referencia']}\n\n**WER:** {fmt_pct(r.get('wer'))}\n")
        if r.get("respuesta"):
            md.append(f"\n**Respuesta del modelo:**\n\n{r['respuesta']}\n")
    comun.guardar_texto("5_audio_transcripcion.md", "".join(md))
    comun.guardar_json("5_audio_transcripcion.json", resultados)


if __name__ == "__main__":
    main()
