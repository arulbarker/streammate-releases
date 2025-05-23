import requests
import json
from datetime import datetime
import hashlib
import hmac

# LANGSUNG MASUKKAN KREDENSIAL SANDBOX ANDA DI SINI
ipaymuVa  = "0000009516425913"
ipaymuKey = "SANDBOXE1498BCD-9D73-4607-A2EB-FA78939BBC45"
# ----------------------------------------------------

# Untuk check balance, endpoint dan body berbeda
# ipaymuUrl = "https://sandbox.ipaymu.com/api/v2/transaction"
# body =  {
#             "transactionId":"78174" # Ganti dengan ID transaksi yang valid jika ada
#         }

# Mari kita coba endpoint balance seperti di _test_connection Anda
ipaymuUrl = "https://sandbox.ipaymu.com/api/v2/balance"
body = {
    "account": ipaymuVa
}

print(f"Menggunakan VA: {ipaymuVa}")
print(f"Menggunakan API Key: {ipaymuKey}")
print(f"Menggunakan URL: {ipaymuUrl}")
print(f"Body Request: {body}")

# data_body    = json.dumps(body) # ini akan menghasilkan spasi setelah : dan ,
data_body    = json.dumps(body, separators=(',', ':')) # lebih aman, tanpa spasi ekstra
print(f"JSON Body String: {data_body}")

encrypt_body = hashlib.sha256(data_body.encode()).hexdigest() # TANPA .lower()
print(f"Encrypted Body: {encrypt_body}")

stringtosign = "{}:{}:{}:{}".format("POST", ipaymuVa, encrypt_body, ipaymuKey)
print(f"String-to-Sign: {stringtosign}")

signature    = hmac.new(ipaymuKey.encode(), stringtosign.encode(), hashlib.sha256).hexdigest().lower()
print(f"Generated Signature: {signature}")

timestamp    = datetime.today().strftime('%Y%m%d%H%M%S')
print(f"Timestamp: {timestamp}")

headers = {
    'Content-type': 'application/json',
    'Accept': 'application/json',
    'signature': signature,
    'va':ipaymuVa,
    'timestamp':timestamp
}
print(f"Headers: {headers}")

try:
    response = requests.post(ipaymuUrl, headers=headers, data=data_body)
    print("\n--- RESPONSE ---")
    print(f"Status Code: {response.status_code}")
    print(f"Response Text: {response.text}")
except Exception as e:
    print(f"Error saat request: {e}")