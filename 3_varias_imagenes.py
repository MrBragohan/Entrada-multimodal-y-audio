"""Parte 1.3 — Varias imágenes relacionadas en UNA solicitud (comparación o resumen conjunto).

El modelo admite como máximo 3 imágenes y 20 MB por solicitud (cada imagen cuenta como 2.048
tokens de entrada). Este script comprueba esos límites antes de enviar; la parte 4 los rompe a
propósito.

Uso:
    python 3_varias_imagenes.py                                  # eliges 2 o 3 de una lista
    python 3_varias_imagenes.py --imagenes tabla.png grafico.png
    python 3_varias_imagenes.py --imagenes a.png b.png --pregunta "¿Qué relación hay entre ellas?"
"""
import argparse

import groq

import comun

PREGUNTA_DEFECTO = ("Estas imágenes están relacionadas. Compáralas: ¿qué tienen en común, en qué "
                    "se diferencian y cómo se complementan para explicar un sistema de IA? "
                    "Haz un resumen conjunto en pocas líneas.")


def elegir_varias():
    imagenes = comun.listar_imagenes()
    if len(imagenes) < 2:
        raise SystemExit(f"Se necesitan al menos 2 imágenes en {comun.CARPETA_IMAGENES}.")
    for i, img in enumerate(imagenes, 1):
        print(f"  {i}. {img.name}")
    txt = input("Números de 2 o 3 imágenes separados por coma [1,2]: ").strip() or "1,2"
    return [imagenes[int(n) - 1] for n in txt.split(",")]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--imagenes", nargs="+", help="2 o 3 imágenes (nombre en imagenes/ o ruta)")
    p.add_argument("--pregunta", default=PREGUNTA_DEFECTO)
    args = p.parse_args()

    rutas = [comun.resolver_imagen(n) for n in args.imagenes] if args.imagenes else elegir_varias()
    if len(rutas) < 2:
        raise SystemExit("Indica al menos 2 imágenes para compararlas.")

    problemas = comun.validar_solicitud_imagenes(rutas)
    if problemas:
        raise SystemExit("No se envía la solicitud: " + " ".join(problemas))

    print(f"\nImágenes: {[r.name for r in rutas]}")
    print(f"Modelo  : {comun.MODELO_VISION}  (≈{2048 * len(rutas)} tokens de entrada solo por las imágenes)")
    print(f"Pregunta: {args.pregunta}")

    try:
        respuesta = comun.llamar_chat([comun.mensaje_usuario(args.pregunta, rutas)],
                                      comun.MODELO_VISION)
    except groq.APIError as e:
        comun.salir_por_error_api(e)

    print(f"\nRespuesta:\n{respuesta}")

    miniaturas = "\n\n".join(f"![{r.name}](../imagenes/{r.name})" for r in rutas)
    comun.guardar_texto("3_varias_imagenes.md", (
        f"# Parte 1.3 — Varias imágenes en una solicitud\n\n"
        f"- Fecha: {comun.sello()}\n- Modelo: `{comun.MODELO_VISION}`\n"
        f"- Imágenes en la solicitud: {len(rutas)}\n\n## Imágenes\n\n{miniaturas}\n\n"
        f"## Pregunta\n\n{args.pregunta}\n\n## Respuesta del modelo\n\n{respuesta}\n"
    ))


if __name__ == "__main__":
    main()
