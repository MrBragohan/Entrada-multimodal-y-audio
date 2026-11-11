# Parte 2 — Audio y transcripción

- Fecha: 2026-11-11 13:26
- Whisper: `whisper-large-v3-turbo` | Respuesta: `qwen/qwen3.8-27b`
- Audios transcritos: 2/2
- Segundos facturados (mínimo 10 s por solicitud): 40 s
- **WER medio:** 7.5 % (2 audios con referencia)
- WER sin ruido de fondo: 7.5 % (2 audios)

## audio_01.wav

- Hablante: ? | Ruido de fondo: False | Duración: 20.0 s

**Transcripción:** que es el chunking en un sistema rack y como influye el tamaño del fragmento en la recuperación del contexto

**Texto real:** ¿Qué es el chunking en un sistema RAG y cómo influye el tamaño del fragmento en la recuperación del contexto?

**WER:** 15.0 %

**Respuesta del modelo:**

# Chunking en un Sistema RAG

## ¿Qué es?

El **chunking** es el proceso de dividir un documento largo en fragmentos (chunks) más pequeños antes de indexarlos en la base de vectores. Es el paso previo a la vectorización.

```
Documento largo → [Chunk 1] [Chunk 2] [Chunk 3] ... → Embeddings → Base de vectores
```

## ¿Por qué se hace?

- Los modelos de embedding tienen un **límite de tokens** de entrada.
- Un documento completo diluye la semántica; un chunk enfoca el significado.
- Permite recuperar **solo la parte relevante** en vez de todo el documento.

## Influencia del tamaño del fragmento

| Tamaño | Ventaja | Desventaja |
|--------|---------|------------|
| **Muy pequeño** (50-100 tokens) | Alta precisión semántica, recuperación exacta | Pierde contexto, puede fragmentar ideas, más chunks = más ruido |
| **Medio** (256-512 tokens) | Equilibrio entre contexto y precisión | Puede no capturar relaciones lejanas |
| **Muy grande** (1000+ tokens) | Mantiene contexto completo | Diluye el embedding, recupera información irrelevante, consume más tokens del LLM |

## Efecto concreto en la recuperación

```
Chunk pequeño:  "La API usa autenticación OAuth2."
                 → Embedding muy específico → solo recupera si la query menciona OAuth2

Chunk grande:   "La API usa autenticación OAuth2. Los tokens expiran en 1h.
                 Para renovar, se usa el refresh_token en /auth/refresh..."
                 → Embedding más general → puede recuperar para queries sobre
                   tokens, expiración, renovación, etc.
```

## Estrategias comunes

- **Fijo**: dividir cada N tokens (simple pero rígido).
- **Por estructura**: usar encabezados, párrafos o secciones como límites.
- **Con solapamiento (overlap)**: repetir los últimos X tokens del chunk anterior al inicio del siguiente, para no cortar ideas a la mitad.

```
[Chunk 1: tokens 0-512]
[Chunk 2: tokens 448-960]   ← overlap de 64 tokens
[Chunk 3: tokens 896-1408]
```

## Regla práctica

> **Empieza con 256-512 tokens y 10-20% de overlap.** Ajusta según el dominio: documentos técnicos densos suelen funcionar mejor con chunks más pequeños; documentos narrativos o de contexto amplio, con chunks más grandes.

El tamaño óptimo siempre depende del **tipo de query** que esperes recibir. Si las preguntas son específicas → chunks pequeños. Si son de alto nivel → chunks más grandes.

## audio_02.wav

- Hablante: ? | Ruido de fondo: False | Duración: 20.0 s

**Transcripción:** ¿Cómo se mide la fidelidad de una respuesta con ragas? ¿Y qué significa la métrica Faithfulness?

**Texto real:** ¿Cómo se mide la fidelidad de una respuesta con Ragas y qué significa la métrica faithfulness?

**WER:** 0.0 %

**Respuesta del modelo:**

## Faithfulness en RAGAS

### ¿Qué mide?

**Faithfulness** mide si la respuesta generada es **factualmente consistente** con el contexto recuperado. Es decir, verifica que la respuesta no invente información que no está en los documentos recuperados.

### ¿Cómo se calcula?

El proceso es:

1. **Descomposición** → Se extraen las afirmaciones (claims) individuales de la respuesta generada.
2. **Verificación** → Cada afirmación se contrasta contra el contexto recuperado para determinar si es inferible de él.
3. **Cálculo** →

$$\text{Faithfulness} = \frac{\text{Afirmaciones soportadas por el contexto}}{\text{Total de afirmaciones en la respuesta}}$$

### Ejemplo

| Afirmación en la respuesta | ¿Soportada por el contexto? |
|---|---|
| "El sistema usa PostgreSQL" | ✅ Sí |
| "La latencia es de 50ms" | ✅ Sí |
| "El sistema soporta 10,000 usuarios" | ❌ No aparece en el contexto |

**Faithfulness = 2/3 ≈ 0.67**

### Interpretación

| Valor | Significado |
|-------|-------------|
| 1.0 | La respuesta es 100% fiel al contexto (no hay alucinaciones) |
| 0.0 | Ninguna afirmación está soportada (respuesta completamente inventada) |

### Diferencia clave con otras métricas de RAGAS

- **Faithfulness** → ¿La respuesta se basa en el contexto? (evita alucinaciones)
- **Answer Relevancy** → ¿La respuesta responde a la pregunta?
- **Context Precision** → ¿El contexto recuperado es relevante?
- **Context Recall** → ¿El contexto recuperado cubre la información necesaria?

### En resumen

> Faithfulness responde a: *"¿El modelo se inventó algo que no estaba en los documentos que le pasaste?"*

Es la métrica más directa para detectar **alucinaciones** en pipelines RAG.
