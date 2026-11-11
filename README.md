# Taller: entrada multimodal y audio

Visión y voz a texto aplicadas al dominio del proyecto (**Tutor Académico de Creación de
Aplicaciones con IA**): figuras, tablas y capturas técnicas como imágenes; preguntas habladas con
términos del dominio (RAG, embeddings, chunking, Ragas…) como audio.

| Componente | Modelo por defecto (Groq) |
|---|---|
| Visión | `qwen/qwen3.8-27b` |
| Voz a texto | `whisper-large-v3-turbo` |
| Respuesta al audio | `qwen/qwen3.8-27b` |

## Instalación

```bash
pip install -r requirements.txt
copy .env.example .env        # Windows (Mac/Linux: cp) y escribe tu GROQ_API_KEY
```

### Variables de entorno (archivo `.env`, nunca en el código)

| Variable | Obligatoria | Para qué |
|---|---|---|
| `GROQ_API_KEY` | Sí | Clave de https://console.groq.com |
| `VISION_MODEL`, `STT_MODEL`, `TEXT_MODEL` | No | Cambiar de modelo (nombre exacto) |
| `REASONING_EFFORT` | No | Esfuerzo de razonamiento (por defecto `low`) |
| `MODELO_SIN_VISION` | No | Modelo de solo texto para la parte 1.4 |

Si la API responde *model not found*: `python listar_modelos.py qwen whisper` muestra los nombres
disponibles en tu cuenta.

## Ejecución

Imágenes en `imagenes/` (traen 5 de **ejemplo**: reemplázalas por las del dominio) y audios en `audios/`.

| Parte | Comando | Qué hace |
|---|---|---|
| 1.1 | `python 1_pregunta_imagen.py --imagen X.png --pregunta "..."` | Pregunta sobre una imagen (base64) |
| 1.2 | `python 2_extraccion_estructurada.py` | JSON de 6 campos en 3 imágenes, validación con Pydantic y % de aciertos |
| 1.3 | `python 3_varias_imagenes.py --imagenes A.png B.png` | 2–3 imágenes en una solicitud |
| 1.4 | `python 4_error_provocado.py` | 4 errores provocados (`--escenario todos` añade imagen > 20 MB) |
| 2 | `python grabar_audio.py --hablante Ana` | Graba un WAV y anota hablante, ruido y texto dicho |
| 2 | `python 5_audio_transcripcion.py` | Transcribe, responde y calcula el WER |

Cada script guarda su informe en `resultados/` (`.md` con imagen, pregunta y respuesta; `.json` con los datos).

### Preparar la parte 1.2
Escribe en `ground_truth.json` los valores **reales** que lees en tus 3 imágenes (mismos 6 campos de
`esquema.py`). Un campo cuenta como acierto si su puntaje es ≥ 0,8: los campos exactos puntúan 0 o 1,
el título compara texto parecido y los términos técnicos usan F1 entre listas.

### Preparar la parte 2
Graba ≥ 4 audios de 10 a 30 s, con 2 o más hablantes y al menos uno con `--ruido`. Si escribes lo que
dijiste, se calcula el **WER** (errores de palabras / palabras reales; mayúsculas y puntuación se
ignoran, las tildes cuentan). `--comparar-vocabulario` transcribe cada audio con y sin una pista de
vocabulario técnico para Whisper.

## Límites (Groq; validar si cambias de modelo o proveedor)

- Visión: máx. **3 imágenes** y **20 MB** por solicitud; cada imagen cuenta como 2.048 tokens.
- Audio: hasta **25 MB** (plan gratuito); wav, mp3, m4a, ogg, webm…; se factura un mínimo de **10 s**.

Los scripts comprueban estos límites antes de enviar (salvo la parte 1.4, que los rompe a propósito).

## Seguridad
`.env` está en `.gitignore`. Antes de subir el repositorio, comprueba que no hay claves en el
historial: `git log -p -S "gsk_"`.
