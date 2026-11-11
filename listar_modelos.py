"""Lista los modelos disponibles en tu cuenta de Groq.

Úsalo si la API responde "model not found" o si quieres cambiar de modelo: copia el nombre
exacto a VISION_MODEL, STT_MODEL o TEXT_MODEL en el archivo .env.

    python listar_modelos.py              # todos
    python listar_modelos.py qwen whisper # solo los que contengan esas palabras
"""
import sys

import groq

import comun


def main():
    filtros = [f.lower() for f in sys.argv[1:]]
    try:
        modelos = sorted(m.id for m in comun.cliente().models.list().data)
    except groq.APIError as e:
        comun.salir_por_error_api(e)
    mostrados = [m for m in modelos if not filtros or any(f in m.lower() for f in filtros)]
    print(f"{len(mostrados)} de {len(modelos)} modelos:")
    for m in mostrados:
        marca = ""
        if m == comun.MODELO_VISION:
            marca += "  <- VISION_MODEL"
        if m == comun.MODELO_STT:
            marca += "  <- STT_MODEL"
        if m == comun.MODELO_TEXTO:
            marca += "  <- TEXT_MODEL"
        print(f"  {m}{marca}")
    for nombre, valor in (("VISION_MODEL", comun.MODELO_VISION), ("STT_MODEL", comun.MODELO_STT),
                          ("TEXT_MODEL", comun.MODELO_TEXTO)):
        if valor not in modelos:
            print(f"\n[!] {nombre}='{valor}' NO aparece entre los modelos de tu cuenta.")


if __name__ == "__main__":
    main()
