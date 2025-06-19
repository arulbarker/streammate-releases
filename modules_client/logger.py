from datetime import datetime

log_data = []

def add_log(speaker, message):
    log_data.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "speaker": speaker,
        "message": message
    })

def get_log():
    return log_data

