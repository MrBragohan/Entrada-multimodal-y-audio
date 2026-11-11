"""Parte 1.2 — Extracción estructurada (JSON) de 3 imágenes y precisión campo por campo.

Flujo por imagen:
  1. El modelo con visión extrae los campos del esquema (esquema.py) en JSON.
  2. Se VALIDA con Pydantic: si no cumple el esquema se informa y se sigue con la siguiente imagen.
  3. Se compara con lo que tú lees en la imagen (ground_truth.json) y se calcula el % de aciertos.

Antes de ejecutar, escribe en ground_truth.json los valores reales de tus 3 imágenes
(mira el ejemplo que ya trae el archivo).

Uso:
    python 2_extraccion_estructurada.py
    python 2_extraccion_estructurada.py --imagenes figura1.png tabla2.png grafico3.png
"""
import argparse
import json

import groq

import comun
import esquema

RUTA_GT = comun.BASE / "ground_truth.json"


def cargar_ground_truth():
    if not RUTA_GT.exists():
        return {}
    gt = json.loads(RUTA_GT.read_text(encoding="utf-8"))
    return {k: v for k, v in gt.items() if not k.startswith("_")}


def elegir_imagenes(args, gt):
    if args.imagenes:
        nombres = args.imagenes
    elif gt:
        nombres = list(gt)
    else:
        nombres = [p.name for p in comun.listar_imagenes()]
        print("[!] ground_truth.json no tiene entradas: se extraerá pero NO se podrá medir precisión.")
    if len(nombres) > 3:
        print(f"[!] El taller pide 3 imágenes; se usarán las primeras 3 de {len(nombres)}.")
    return [comun.resolver_imagen(n) for n in nombres[:3]]


def imprimir_tabla(filas):
    print(f"  {'campo':<22}{'esperado':<34}{'extraído':<34}{'puntaje'}")
    for f in filas:
        marca = "✓" if f["acierto"] else "✗"
        esp = json.dumps(f["esperado"], ensure_ascii=False)[:31]
        ext = json.dumps(f["extraido"], ensure_ascii=False)[:31]
        print(f"  {f['campo']:<22}{esp:<34}{ext:<34}{f['puntaje']:.2f} {marca}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--imagenes", nargs="+", help="nombres de las imágenes (máx. 3)")
    args = p.parse_args()

    gt = cargar_ground_truth()
    rutas = elegir_imagenes(args, gt)
    prompt = esquema.construir_prompt()

    print(f"Modelo: {comun.MODELO_VISION} | Campos del esquema: {list(esquema.FichaFigura.model_fields)}")
    resultados, md = [], []

    for ruta in rutas:
        print(f"\n{'=' * 78}\nImagen: {ruta.name}\n{'=' * 78}")
        reg = {"imagen": ruta.name, "valido": False, "errores": [], "extraido": None, "comparacion": None}

        try:
            texto = comun.llamar_chat([comun.mensaje_usuario(prompt, [ruta])],
                                      comun.MODELO_VISION, json_mode=True)
        except groq.APIError as e:
            d = comun.describir_error_api(e)
            reg["errores"] = [f"error de la API: {d['tipo']} (HTTP {d['codigo_http']}): {d['mensaje']}"]
            print(f"✗ {reg['errores'][0]}")
            resultados.append(reg)
            md.append(f"## {ruta.name}\n\n✗ {reg['errores'][0]}\n")
            continue

        reg["respuesta_cruda"] = texto
        ficha, errores = esquema.validar(texto)

        if errores:
            reg["errores"] = errores
            print("✗ El JSON NO cumple el esquema (el programa continúa):")
            for e in errores:
                print(f"    - {e}")
            print(f"  Respuesta cruda del modelo:\n  {texto[:400]}")
            resultados.append(reg)
            md.append(f"## {ruta.name}\n\n✗ No cumple el esquema:\n\n"
                      + "\n".join(f"- {e}" for e in errores) + "\n")
            continue

        reg["valido"], reg["extraido"] = True, ficha
        print("✓ JSON válido según el esquema:")
        print(json.dumps(ficha, ensure_ascii=False, indent=2))

        real = gt.get(ruta.name)
        seccion = f"## {ruta.name}\n\n![{ruta.name}](../imagenes/{ruta.name})\n\n"
        if real is None:
            print("  (sin ground truth para esta imagen: no se mide precisión)")
            md.append(seccion + "```json\n" + json.dumps(ficha, ensure_ascii=False, indent=2) + "\n```\n"
                      "\n_Sin ground truth._\n")
        else:
            faltan = [c for c in esquema.FichaFigura.model_fields if c not in real]
            if faltan:
                print(f"  [!] Al ground truth le faltan campos {faltan}: se cuentan como errores.")
            filas = esquema.comparar(ficha, real)
            reg["comparacion"] = filas
            imprimir_tabla(filas)
            aciertos = sum(f["acierto"] for f in filas)
            print(f"  → {aciertos}/{len(filas)} campos acertados en esta imagen")
            tabla = "| Campo | Esperado (real) | Extraído | Puntaje |\n|---|---|---|---|\n" + "\n".join(
                f"| {f['campo']} | `{json.dumps(f['esperado'], ensure_ascii=False)}` | "
                f"`{json.dumps(f['extraido'], ensure_ascii=False)}` | {f['puntaje']:.2f} "
                f"{'✓' if f['acierto'] else '✗'} |" for f in filas)
            md.append(seccion + tabla + f"\n\n**{aciertos}/{len(filas)} campos acertados.**\n")
        resultados.append(reg)

    # ------------------------------------------------------------------ resumen global
    validas = [r for r in resultados if r["valido"]]
    comparadas = [r for r in resultados if r["comparacion"]]
    print(f"\n{'#' * 78}\nRESUMEN\n{'#' * 78}")
    print(f"Imágenes procesadas      : {len(resultados)}")
    print(f"JSON válido según esquema: {len(validas)}/{len(resultados)}")

    resumen_md = (f"# Parte 1.2 — Extracción estructurada\n\n- Fecha: {comun.sello()}\n"
                  f"- Modelo: `{comun.MODELO_VISION}`\n- Imágenes: {len(resultados)} | "
                  f"JSON válido: {len(validas)}/{len(resultados)}\n")

    if comparadas:
        todas = [f for r in comparadas for f in r["comparacion"]]
        pct = 100 * sum(f["acierto"] for f in todas) / len(todas)
        medio = 100 * sum(f["puntaje"] for f in todas) / len(todas)
        print(f"Campos comparados        : {len(todas)}")
        print(f"PORCENTAJE DE ACIERTOS   : {pct:.1f} %  (campo acertado = puntaje ≥ {esquema.UMBRAL_ACIERTO})")
        print(f"Puntaje medio            : {medio:.1f} %")
        print("\nAciertos por campo:")
        por_campo = {}
        for f in todas:
            por_campo.setdefault(f["campo"], []).append(f["acierto"])
        filas_campo = []
        for campo, lista in por_campo.items():
            print(f"  {campo:<22}{sum(lista)}/{len(lista)}")
            filas_campo.append(f"| {campo} | {sum(lista)}/{len(lista)} |")
        resumen_md += (f"\n**Porcentaje de aciertos: {pct:.1f} %** ({sum(f['acierto'] for f in todas)}/"
                       f"{len(todas)} campos; puntaje medio {medio:.1f} %).\n\n"
                       "| Campo | Aciertos |\n|---|---|\n" + "\n".join(filas_campo) + "\n")
    else:
        print("No hubo imágenes con JSON válido y ground truth: no se puede calcular el porcentaje.")
        resumen_md += "\n_No hubo comparaciones con ground truth._\n"

    comun.guardar_texto("2_extraccion_estructurada.md", resumen_md + "\n" + "\n".join(md))
    comun.guardar_json("2_extraccion_estructurada.json", resultados)


if __name__ == "__main__":
    main()
