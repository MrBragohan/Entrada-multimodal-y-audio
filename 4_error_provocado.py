"""Parte 1.4 — Errores provocados a propósito para entender los límites de la API.

Escenarios:
    sin_vision           un modelo de solo texto recibe una imagen
    demasiadas_imagenes  4 imágenes en una solicitud (el máximo es 3)
    imagen_invalida      bytes que no son una imagen, declarados como image/png
    tipo_mal_declarado   una imagen real declarada con un tipo MIME que no le corresponde
    imagen_grande        ~34 MB en base64 (el máximo por solicitud es 20 MB)  [lento: sube ~34 MB]

Cada escenario muestra el mensaje REAL que devuelve la API. Algunas APIs toleran ciertos
"errores" (p. ej. el tipo mal declarado): si no hay error, el script lo dice.

Uso:
    python 4_error_provocado.py                          # los 4 escenarios rápidos
    python 4_error_provocado.py --escenario sin_vision
    python 4_error_provocado.py --escenario todos        # incluye imagen_grande
"""
import argparse
import os

import groq

import comun

MODELO_SIN_VISION = os.getenv("MODELO_SIN_VISION", "openai/gpt-oss-20b")


def _imagen_base(args):
    imagenes = comun.listar_imagenes()
    if not imagenes and not args.imagen:
        raise SystemExit(f"Copia al menos 1 imagen en {comun.CARPETA_IMAGENES}.")
    return comun.resolver_imagen(args.imagen) if args.imagen else imagenes[0]


def esc_sin_vision(img):
    return MODELO_SIN_VISION, [comun.mensaje_usuario("¿Qué ves en esta imagen?", [img])]


def esc_demasiadas(img):
    # La misma imagen repetida 4 veces: basta para superar el máximo de 3
    return comun.MODELO_VISION, [comun.mensaje_usuario("Describe estas imágenes.", [img] * 4)]


def esc_invalida(img):
    bloque = comun.bloque_imagen_bytes(b"esto es texto, no una imagen", "image/png")
    return comun.MODELO_VISION, [{"role": "user", "content": [
        {"type": "text", "text": "¿Qué ves en esta imagen?"}, bloque]}]


def esc_tipo_mal_declarado(img):
    real = comun.EXT_IMAGEN[img.suffix.lower()]
    falso = "image/jpeg" if real != "image/jpeg" else "image/png"
    print(f"   (la imagen es {real} pero se declara como {falso})")
    bloque = comun.bloque_imagen_bytes(img.read_bytes(), falso)
    return comun.MODELO_VISION, [{"role": "user", "content": [
        {"type": "text", "text": "¿Qué ves en esta imagen?"}, bloque]}]


def esc_grande(img):
    from PIL import Image
    lado = 3000
    print(f"   (generando una imagen de ruido de {lado}x{lado}: no se comprime, pesa ~26 MB)")
    ruido = Image.frombytes("RGB", (lado, lado), os.urandom(lado * lado * 3))
    import io
    buf = io.BytesIO()
    ruido.save(buf, format="PNG")
    print(f"   (PNG de {len(buf.getvalue()) / 1024 / 1024:.1f} MB; en base64 ≈ "
          f"{len(buf.getvalue()) * 4 / 3 / 1024 / 1024:.1f} MB)")
    bloque = comun.bloque_imagen_bytes(buf.getvalue(), "image/png")
    return comun.MODELO_VISION, [{"role": "user", "content": [
        {"type": "text", "text": "¿Qué ves en esta imagen?"}, bloque]}]


ESCENARIOS = {
    "sin_vision": {
        "construir": esc_sin_vision,
        "que_se_hace": f"Se envía una imagen a un modelo SIN visión ({MODELO_SIN_VISION}).",
        "causa": ("Los modelos de solo texto esperan que `content` sea un texto; no reconocen el "
                  "bloque de imagen. Hay que usar un modelo con visión (VISION_MODEL)."),
    },
    "demasiadas_imagenes": {
        "construir": esc_demasiadas,
        "que_se_hace": "Se envían 4 imágenes en un solo mensaje.",
        "causa": (f"El modelo con visión admite como máximo {comun.MAX_IMAGENES} imágenes por "
                  "solicitud; con 4 se supera el límite."),
    },
    "imagen_invalida": {
        "construir": esc_invalida,
        "que_se_hace": "Se envían bytes de texto declarados como image/png.",
        "causa": ("El contenido no se puede decodificar como imagen (no hay una cabecera PNG "
                  "válida), aunque el tipo declarado diga image/png."),
    },
    "tipo_mal_declarado": {
        "construir": esc_tipo_mal_declarado,
        "que_se_hace": "Se envía una imagen real con un tipo MIME que no corresponde a su formato.",
        "causa": ("El tipo declarado no coincide con el contenido real. Algunas APIs detectan el "
                  "formato por el contenido y lo toleran; otras lo rechazan. Si aquí no hubo "
                  "error, ese es el resultado a explicar."),
    },
    "imagen_grande": {
        "construir": esc_grande,
        "que_se_hace": "Se envía una imagen de ~26 MB (≈34 MB en base64).",
        "causa": (f"La solicitud supera el máximo de {comun.MAX_MB_SOLICITUD} MB. Recuerda que el "
                  "base64 aumenta el tamaño del archivo en ~33 %."),
    },
}
RAPIDOS = ["sin_vision", "demasiadas_imagenes", "imagen_invalida", "tipo_mal_declarado"]


def ejecutar(nombre, img):
    info = ESCENARIOS[nombre]
    print(f"\n{'=' * 78}\nEscenario: {nombre}\n{'=' * 78}\n{info['que_se_hace']}")
    modelo, mensajes = info["construir"](img)
    print(f"   Modelo: {modelo}")
    try:
        r = comun.llamar_chat(mensajes, modelo, max_tokens=300, reintentar=False)
        print("\n→ SIN ERROR: la API aceptó la solicitud. Respuesta (recortada):")
        print(f"  {r[:300]}")
        return {"escenario": nombre, "modelo": modelo, "hubo_error": False, "respuesta": r[:300]}
    except groq.APIError as e:
        d = comun.describir_error_api(e)
        print(f"\n→ ERROR de la API\n  Tipo         : {d['tipo']}\n  Código HTTP  : {d['codigo_http']}"
              f"\n  Mensaje      : {d['mensaje']}")
        print(f"\n  Causa esperada (confírmala con el mensaje de arriba):\n  {info['causa']}")
        return {"escenario": nombre, "modelo": modelo, "hubo_error": True, **d}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--escenario", default="rapidos",
                   choices=list(ESCENARIOS) + ["rapidos", "todos"])
    p.add_argument("--imagen", help="imagen base (por defecto, la primera de imagenes/)")
    args = p.parse_args()

    img = _imagen_base(args)
    if args.escenario == "rapidos":
        nombres = RAPIDOS
    elif args.escenario == "todos":
        nombres = list(ESCENARIOS)
    else:
        nombres = [args.escenario]

    resultados = [ejecutar(n, img) for n in nombres]

    md = [f"# Parte 1.4 — Errores provocados\n\n- Fecha: {comun.sello()}\n"
          f"- Modelo con visión: `{comun.MODELO_VISION}` | Imagen base: `{img.name}`\n"]
    for r in resultados:
        info = ESCENARIOS[r["escenario"]]
        md.append(f"\n## {r['escenario']}\n\n**Qué se hizo:** {info['que_se_hace']}\n")
        if r["hubo_error"]:
            md.append(f"\n**Mensaje de la API** (`{r['tipo']}`, HTTP {r['codigo_http']}):\n\n"
                      f"```\n{r['mensaje']}\n```\n\n**Causa:** {info['causa']}\n")
        else:
            md.append(f"\n**Resultado:** la API NO devolvió error y respondió: _{r['respuesta']}_\n\n"
                      f"**Por qué:** {info['causa']}\n")
    comun.guardar_texto("4_error_provocado.md", "".join(md))
    comun.guardar_json("4_error_provocado.json", resultados)


if __name__ == "__main__":
    main()
