import requests

def cek_saldo_trakteer(api_key):
    url = "https://api.trakteer.id/v1/public/current-balance"
    headers = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "key": api_key
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data["status"] == "success":
            saldo = data["result"]
            print(f"💰 Saldo Trakteer saat ini: Rp{saldo}")
            return saldo
        else:
            print(f"[ERROR] Gagal mendapatkan saldo: {data.get('message')}")
            return None
    except requests.RequestException as e:
        print(f"[ERROR] Koneksi gagal: {str(e)}")
        return None
