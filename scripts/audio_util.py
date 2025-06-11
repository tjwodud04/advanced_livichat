# audio_util.py
import numpy as np
from ffmpeg import FFmpeg

def convert_webm_to_pcm16(webm_data: bytes):
    """
    ffmpeg-python의 표준 .run() API로 WebM → 24kHz 모노 16bit PCM 변환
    """
    try:
        ffmpeg = (
            FFmpeg()
            .input("pipe:0")
            .output("pipe:1",
                    format="s16le",
                    acodec="pcm_s16le",
                    ac=1,
                    ar=24000)
        )
        out, _ = ffmpeg.run(input=webm_data)
        samples = np.frombuffer(out, dtype=np.int16)
        return samples
    except Exception as e:
        print(f"[convert_webm_to_pcm16] Audio conversion error: {e}")
        return None
