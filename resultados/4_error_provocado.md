# Parte 1.4 — Errores provocados

- Fecha: 2026-11-11 13:13
- Modelo con visión: `qwen/qwen3.8-27b` | Imagen base: `ejemplo_01_arquitectura_rag.png`

## sin_vision

**Qué se hizo:** Se envía una imagen a un modelo SIN visión (openai/gpt-oss-20b).

**Mensaje de la API** (`BadRequestError`, HTTP 400):

```
Error code: 400 - {'error': {'message': 'messages[0].content must be a string', 'type': 'invalid_request_error', 'param': 'messages[0].content'}}
```

**Causa:** Los modelos de solo texto esperan que `content` sea un texto; no reconocen el bloque de imagen. Hay que usar un modelo con visión (VISION_MODEL).

## demasiadas_imagenes

**Qué se hizo:** Se envían 4 imágenes en un solo mensaje.

**Mensaje de la API** (`BadRequestError`, HTTP 400):

```
Error code: 400 - {'error': {'message': 'Too many images provided.  This model supports up to 3 images', 'type': 'invalid_request_error'}}
```

**Causa:** El modelo con visión admite como máximo 3 imágenes por solicitud; con 4 se supera el límite.

## imagen_invalida

**Qué se hizo:** Se envían bytes de texto declarados como image/png.

**Mensaje de la API** (`BadRequestError`, HTTP 400):

```
Error code: 400 - {'error': {'message': 'invalid image data', 'type': 'invalid_request_error'}}
```

**Causa:** El contenido no se puede decodificar como imagen (no hay una cabecera PNG válida), aunque el tipo declarado diga image/png.

## tipo_mal_declarado

**Qué se hizo:** Se envía una imagen real con un tipo MIME que no corresponde a su formato.

**Resultado:** la API NO devolvió error y respondió: _En la imagen veo un **diagrama de flujo** titulado **"Arquitectura del pipeline RAG"** (RAG = *Retrieval‑Augmented Generation*), que ilustra las etapas de un sistema de generación aumentada por recuperación. El diagrama está compuesto por seis bloques redondeados de distintos colores, unidos por fle_

**Por qué:** El tipo declarado no coincide con el contenido real. Algunas APIs detectan el formato por el contenido y lo toleran; otras lo rechazan. Si aquí no hubo error, ese es el resultado a explicar.
