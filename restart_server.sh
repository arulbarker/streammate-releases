#!/bin/bash
cd /root/streammateai_server
pkill -f uvicorn
sleep 2
python3 -m uvicorn server_inti:app --host 0.0.0.0 --port 8000 --reload --log-level info > server.log 2>&1 &
echo "Server restarted"
sleep 3
curl -X GET http://localhost:8000/api/health 