import os
import logging
from pathlib import Path

# ─── Super Direct Google STT only - Whisper removed ─────────────
logger = logging.getLogger('StreamMate')
TRIGGER_FILE = Path("temp/trigger.txt")

# ─── Google STT Integration ────────────────────────────────────────
from google.cloud import speech

# mapping kode BCP-47 ke Google Speech
_GOOGLE_LANG_MAP = {
    "ind_Latn": "id-ID",
    "jpn_Jpan": "ja-JP", 
    "zho_Hans": "zh",
    "kor_Hang": "ko-KR",
    "arb_Arab": "ar-XA",
}

def _google_transcribe(wav_path: str, src_lang: str = "ind_Latn") -> str | None:
    """
    Transkrip file WAV menggunakan Google Cloud Speech-to-Text.
    Pastikan env var GOOGLE_APPLICATION_CREDENTIALS sudah diset.
    """
    try:
        client = speech.SpeechClient()
        with open(wav_path, "rb") as f:
            content = f.read()
        audio = speech.RecognitionAudio(content=content)
        language_code = _GOOGLE_LANG_MAP.get(src_lang, "en-US")
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
        )
        response = client.recognize(config=config, audio=audio)
        texts = [res.alternatives[0].transcript for res in response.results]
        return " ".join(texts) if texts else None
    except Exception as e:
        print(f"Google STT Error: {e}")
        return None

def transcribe(wav_path: str, src_lang: str = "ind_Latn", use_google: bool = True) -> str | None:
    """
    STT transcription using Google Cloud Speech only (Whisper removed)
    """
    logger.info(f"STT started: {wav_path} (lang={src_lang}, google={use_google})")
    
    # Always use Google STT now (Whisper removed)
    result = _google_transcribe(wav_path, src_lang)
    
    # Track credit usage
    try:
        from modules_server.real_credit_tracker import credit_tracker
        import soundfile as sf
        
        # Calculate audio duration
        try:
            data, samplerate = sf.read(wav_path)
            duration_seconds = len(data) / samplerate
        except Exception as audio_error:
            # Fallback if audio file error
            file_size = os.path.getsize(wav_path) if os.path.exists(wav_path) else 0
            duration_seconds = max(1.0, file_size / 32000)  # Estimate 16kHz 16bit
        
        # Track as Google STT usage
        credits_used = credit_tracker.track_stt_usage(duration_seconds, "google_stt")
        
        logger.info(f"STT completed and tracked: {duration_seconds:.1f}s (google_stt) = {credits_used:.4f} credits")
        
    except Exception as tracking_error:
        logger.error(f"STT tracking failed: {tracking_error}")
        # Don't fail STT just because of tracking error
    
    return result