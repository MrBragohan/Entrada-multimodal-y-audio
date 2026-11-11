"""Graba un audio corto desde el micrófono y lo guarda como WAV en audios/.

Uso:
    python grabar_audio.py --hablante Ana                     # 20 s -> audios/audio_01.wav
    python grabar_audio.py --hablante Luis --ruido            # marca que hay ruido de fondo
    python grabar_audio.py --hablante Ana --segundos 15 --nombre pregunta_chunking.wav

El taller pide al menos 4 audios de 10 a 30 s, con 2 o más personas distintas hablando y al
menos uno con ruido de fondo, usando términos técnicos del dominio (RAG, embeddings,
chunking, Ragas...). Al terminar puedes escribir lo que dijiste: se guarda en
audios/referencias.json y permite calcular el WER (calidad de la transcripción).
"""
import argparse
import json
import re
import time

import comun

FRECUENCIA = 16000  # Whisper trabaja a 16 kHz: archivos pequeños y sin pérdida de calidad útil


def siguiente_nombre():
    usados = [int(m.group(1)) for p in comun.CARPETA_AUDIOS.glob("audio_*.wav")
              if (m := re.match(r"audio_(\d+)\.wav", p.name))]
    return f"audio_{max(usados, default=0) + 1:02d}.wav"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--segundos", type=int, default=20, help="duración (10 a 30 recomendado)")
    p.add_argument("--nombre", help="nombre del archivo (por defecto audio_NN.wav)")
    p.add_argument("--hablante", default="?", help="quién habla (para el informe)")
    p.add_argument("--ruido", action="store_true", help="indica que hay ruido de fondo")
    p.add_argument("--no-reproducir", action="store_true", help="no reproducir al terminar")
    args = p.parse_args()

    try:
        import sounddevice as sd
        from scipy.io.wavfile import write
    except (ImportError, OSError) as e:
        raise SystemExit(f"No se pudo cargar sounddevice/scipy ({e}). Instala: "
                         "pip install sounddevice scipy  (en Linux: sudo apt install libportaudio2)")

    comun.CARPETA_AUDIOS.mkdir(exist_ok=True)
    nombre = args.nombre or siguiente_nombre()
    if not nombre.lower().endswith(".wav"):
        nombre += ".wav"
    ruta = comun.CARPETA_AUDIOS / nombre

    if not 10 <= args.segundos <= 30:
        print(f"[!] El taller pide audios de 10 a 30 s (elegiste {args.segundos} s). "
              "Recuerda además que Groq factura un mínimo de 10 s por solicitud.")

    input(f"\nHablante: {args.hablante} | ruido: {'sí' if args.ruido else 'no'} | "
          f"{args.segundos} s.\nPulsa Enter y empieza a hablar...")
    print("Grabando...")
    audio = sd.rec(int(args.segundos * FRECUENCIA), samplerate=FRECUENCIA, channels=1, dtype="int16")
    for restante in range(args.segundos, 0, -1):
        print(f"  {restante:>2} s", end="\r", flush=True)
        time.sleep(1)
    sd.wait()
    print("Listo.        ")

    write(ruta, FRECUENCIA, audio)
    print(f"Guardado: {ruta} ({ruta.stat().st_size / 1024:.0f} KB)")

    if not args.no_reproducir:
        print("Reproduciendo...")
        sd.play(audio, samplerate=FRECUENCIA)
        sd.wait()

    dicho = input("\nEscribe EXACTAMENTE lo que dijiste (Enter para omitir): ").strip()
    ruta_ref = comun.CARPETA_AUDIOS / "referencias.json"
    refs = json.loads(ruta_ref.read_text(encoding="utf-8")) if ruta_ref.exists() else {}
    refs[nombre] = {"texto": dicho, "hablante": args.hablante, "ruido": args.ruido}
    ruta_ref.write_text(json.dumps(refs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Metadatos guardados en {ruta_ref.name}")


if __name__ == "__main__":
    main()
