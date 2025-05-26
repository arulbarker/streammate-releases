# modules/nlbb_translator.py
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch

model_name = "facebook/nllb-200-distilled-600M"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model     = AutoModelForSeq2SeqLM.from_pretrained(model_name)

# Mapping kode bahasa ke token ID
# pada NLLB biasanya tersedia di tokenizer.lang2id
lang2id = getattr(tokenizer, "lang2id", {})

def translate_id_to_en(text: str) -> str:
    """
    Terjemahkan teks Indonesia → Inggris menggunakan NLLB offline.
    """
    # Prepend token untuk source lang
    input_text = f"<2ind_Latn> {text}"
    inputs = tokenizer(input_text, return_tensors="pt")
    # Forced BOS token ID untuk target lang
    bos = lang2id.get("eng_Latn")
    outputs = model.generate(**inputs, forced_bos_token_id=bos)
    return tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
