import keyboard
import speech_recognition as sr
import json
from modules.cohost_engine import respond_with_voice

def listen_to_mic_and_respond():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    print("🎤 Mendengarkan...")
    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)

    try:
        text = recognizer.recognize_google(audio, language="id-ID")
        print(f"🗣️ Kamu bilang: {text}")

        # Baca konfigurasi untuk menentukan interaction_mode
        with open("config/settings.json", "r") as f:
            config = json.load(f)

        if config.get("interaction_mode", "Ngobrol") == "Terjemahkan ke Inggris":
            # Ubah prompt untuk terjemahan ke bahasa Inggris
            prompt = f"Tolong terjemahkan ke bahasa Inggris: {text}"
        else:
            prompt = text

        respond_with_voice(prompt)

    except sr.UnknownValueError:
        print("😅 Tidak bisa mengenali ucapan.")
    except sr.RequestError as e:
        print(f"❌ Error STT: {e}")

def run_shortcut_listener(shortcut="ctrl+alt+x"):
    print(f"⏳ Menunggu shortcut: {shortcut}")
    keyboard.add_hotkey(shortcut, listen_to_mic_and_respond)
    keyboard.wait()  # Menunggu terus sampai user menghentikan program

if __name__ == '__main__':
    # Jika ingin menguji secara langsung, pastikan shortcut diambil dari settings
    try:
        with open("config/settings.json", "r") as f:
            config = json.load(f)
        shortcut = config.get("shortcut", "ctrl+alt+x")
    except Exception:
        shortcut = "ctrl+alt+x"
    run_shortcut_listener(shortcut)
