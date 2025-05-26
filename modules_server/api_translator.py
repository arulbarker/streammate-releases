# modules_server/api_translator.py

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline

MODEL_NAME = "facebook/nllb-200-distilled-600M"

# Load model sekali saja
_tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
_model     = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

def translate_dynamic(text: str, src_lang: str, tgt_lang: str) -> str | None:
    """
    Terjemahkan teks dari src_lang ke tgt_lang menggunakan NLLB-200.
    Contoh: src_lang="ind_Latn", tgt_lang="eng_Latn".
    """
    try:
        translator = pipeline(
            "translation",
            model=_model,
            tokenizer=_tokenizer,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            device=0 if __import__("torch").cuda.is_available() else -1
        )
        result = translator(text, max_length=512)
        return result[0]["translation_text"]
    except Exception as e:
        print(f"❌ NLLB translate_dynamic Error: {e}")
        return None
