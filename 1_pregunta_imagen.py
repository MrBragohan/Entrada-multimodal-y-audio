"""Parte 1.1 — Pregunta sobre una imagen del dominio (imagen local enviada en base64).

Uso:
    python 1_pregunta_imagen.py                          # elige la imagen de una lista
    python 1_pregunta_imagen.py --imagen mi_figura.png --pregunta "¿Qué muestra esta tabla?"
    python 1_pregunta_imagen.py --imagen mi_figura.png --mostrar   # abre la imagen en pantalla

Guarda un informe con la pregunta, la imagen y la respuesta en resultados/1_pregunta_imagen.md
"""
import argparse

import groq

import comun

PREGUNTA_DEFECTO = ("Describe qué muestra esta figura y explica qué conceptos de Creación de "
                    "Aplicaciones con IA ilustra.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--imagen", help="nombre dentro de imagenes/ o ruta; si se omite, se elige de una lista")
    p.add_argument("--pregunta", default=PREGUNTA_DEFECTO)
    p.add_argument("--mostrar", action="store_true", help="abre la imagen con el visor del sistema")
    args = p.parse_args()

    ruta = comun.resolver_imagen(args.imagen) if args.imagen else comun.elegir_imagen()

    problemas = comun.validar_solicitud_imagenes([ruta])
    if problemas:
        raise SystemExit("No se envía la solicitud: " + " ".join(problemas))

    print(f"\nImagen  : {ruta.name}")
    print(f"Modelo  : {comun.MODELO_VISION}")
    print(f"Pregunta: {args.pregunta}")
    if args.mostrar:
        from PIL import Image
        Image.open(ruta).show()

    try:
        respuesta = comun.llamar_chat([comun.mensaje_usuario(args.pregunta, [ruta])],
                                      comun.MODELO_VISION)
    except groq.APIError as e:
        comun.salir_por_error_api(e)

    print(f"\nRespuesta:\n{respuesta}")

    comun.guardar_texto("1_pregunta_imagen.md", (
        f"# Parte 1.1 — Pregunta sobre una imagen\n\n"
        f"- Fecha: {comun.sello()}\n- Modelo: `{comun.MODELO_VISION}`\n\n"
        f"## Imagen\n\n![{ruta.name}](../imagenes/{ruta.name})\n\n"
        f"## Pregunta\n\n{args.pregunta}\n\n## Respuesta del modelo\n\n{respuesta}\n"
    ))


if __name__ == "__main__":
    main()
