import speech_recognition as sr
from modules.tts_engine import speak

def listen_shortcut_and_respond(voice_lang, voice_gender):
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    print("🎤 Shortcut listener aktif...")

    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
        print("🎧 Silakan bicara...")
        audio = recognizer.listen(source)

    try:
        text = recognizer.recognize_google(audio, language="id-ID")
        print(f"🗣️ Kamu bilang: {text}")

        # Langsung balas dengan suara
        speak(f"{text}", voice_lang, voice_gender)

    except sr.UnknownValueError:
        print("😅 Maaf, tidak bisa mengenali ucapan.")
    except sr.RequestError as e:
        print(f"❌ Error STT: {e}")
