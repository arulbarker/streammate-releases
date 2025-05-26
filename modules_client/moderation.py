# modules/moderation.py

TOXIC_KEYWORDS = [
    "bodoh", "goblok", "anjing", "bangsat", "tolol", "babi", "idiot", "ngentot", "kontol"
]

def is_toxic(text):
    text = text.lower()
    for word in TOXIC_KEYWORDS:
        if word in text:
            return True
    return False
