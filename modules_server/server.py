# modules_server/server.py - Final Version dengan Billing Security
import base64
import json
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from modules_server.deepseek_ai import generate_reply
from modules_server.tts_engine import speak
from modules_server.logger_server import log_request, log_error
from modules_server.billing_security import billing_db

app = FastAPI(title="StreamMate AI Server", version="1.0.0")

# ========== EXISTING ENDPOINTS ==========
@app.post("/ai_reply")
async def ai_reply(request: Request):
    try:
        data = await request.json()
        text = data.get("text", "")
        reply = generate_reply(text)
        log_request("ai_reply", {"text": text}, reply)
        return {"reply": reply}
    except Exception as e:
        log_error("ai_reply", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/speak")
async def speak_text(request: Request):
    try:
        data = await request.json()
        text = data.get("text", "")
        voice = data.get("voice", "id-ID-Standard-A")
        # speak() harus mengembalikan audio dalam bentuk base64 string
        audio_base64 = speak(text, voice_name=voice)
        log_request("speak", {"text": text, "voice": voice}, "audio:base64")
        # kembalikan byte audio asli
        return base64.b64decode(audio_base64)
    except Exception as e:
        log_error("speak", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})

# ========== BILLING SECURITY ENDPOINTS ==========

@app.post("/api/demo/check")
async def check_demo_usage(request: Request):
    """
    Cek apakah user masih bisa menggunakan demo hari ini.
    Request: {"email": "user@example.com"}
    Response: {"can_demo": true/false, "remaining_demos": 1, "next_reset": "2025-05-23T00:00:00"}
    """
    try:
        data = await request.json()
        email = data.get("email", "").strip().lower()
        
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        
        result = billing_db.check_demo_usage(email)
        log_request("demo_check", {"email": email}, f"can_demo: {result['can_demo']}")
        
        return {
            "success": True,
            **result
        }
        
    except Exception as e:
        log_error("demo_check", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/demo/register")
async def register_demo_usage(request: Request):
    """
    Register demo usage untuk user.
    Request: {"email": "user@example.com"}
    Response: {"success": true, "demo_expires": "2025-05-22T15:30:00"}
    """
    try:
        data = await request.json()
        email = data.get("email", "").strip().lower()
        
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        
        result = billing_db.register_demo_usage(email)
        
        if not result["success"]:
            return JSONResponse(
                status_code=400, 
                content={
                    "error": result["message"], 
                    "can_retry_tomorrow": result.get("can_retry_tomorrow", False)
                }
            )
        
        log_request("demo_register", {"email": email}, f"expires: {result['demo_expires']}")
        
        return {
            "success": True,
            "demo_expires": result["demo_expires"],
            "duration_minutes": result["duration_minutes"],
            "message": "Demo registered successfully"
        }
        
    except Exception as e:
        log_error("demo_register", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/session/start")
async def start_session(request: Request):
    """
    Start user session tracking.
    Request: {"email": "user@example.com", "feature": "translate", "session_id": "unique_id"}
    Response: {"success": true, "session_id": "generated_or_provided_id"}
    """
    try:
        data = await request.json()
        email = data.get("email", "").strip().lower()
        feature_name = data.get("feature", "general")
        session_id = data.get("session_id")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        
        result = billing_db.start_session(email, feature_name, session_id)
        log_request("session_start", {"email": email, "feature": feature_name}, result["session_id"])
        
        return {
            "success": True,
            "session_id": result["session_id"],
            "feature": feature_name,
            "start_time": result["start_time"]
        }
        
    except Exception as e:
        log_error("session_start", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/session/heartbeat")
async def session_heartbeat(request: Request):
    """
    Send heartbeat untuk active session.
    Request: {"session_id": "session_id", "active_seconds": 120.5}
    Response: {"success": true, "total_active_time": 360.5}
    """
    try:
        data = await request.json()
        session_id = data.get("session_id", "")
        active_seconds = float(data.get("active_seconds", 0))
        
        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID is required")
        
        result = billing_db.heartbeat_session(session_id, active_seconds)
        
        if not result["success"]:
            return JSONResponse(status_code=404, content={"error": result["message"]})
        
        log_request("session_heartbeat", {
            "session_id": session_id[-8:], 
            "active_seconds": active_seconds
        }, f"total: {result['total_active_time']:.1f}s")
        
        return {
            "success": True,
            "session_id": session_id,
            "total_active_time": result["total_active_time"],
            "last_heartbeat": result["last_heartbeat"]
        }
        
    except Exception as e:
        log_error("session_heartbeat", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/session/end")
async def end_session(request: Request):
    """
    End user session dan calculate final usage.
    Request: {"session_id": "session_id"}
    Response: {"success": true, "total_minutes": 5.5, "credited_minutes": 6}
    """
    try:
        data = await request.json()
        session_id = data.get("session_id", "")
        
        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID is required")
        
        result = billing_db.end_session(session_id)
        
        if not result["success"]:
            return JSONResponse(status_code=404, content={"error": result["message"]})
        
        log_request("session_end", {
            "session_id": session_id[-8:], 
            "email": result["email"], 
            "feature": result["feature"]
        }, f"minutes: {result['credited_minutes']}")
        
        return {
            "success": True,
            "session_id": session_id,
            "email": result["email"],
            "feature": result["feature"],
            "total_minutes": result["total_minutes"],
            "credited_minutes": result["credited_minutes"],
            "end_time": result["end_time"]
        }
        
    except Exception as e:
        log_error("session_end", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/license/validate")
async def validate_license_server(request: Request):
    """
    Server-side license validation dengan caching.
    Request: {"email": "user@example.com", "force_refresh": false}
    Response: {"is_valid": true, "tier": "basic", "expire_date": "2025-06-22", ...}
    """
    try:
        data = await request.json()
        email = data.get("email", "").strip().lower()
        force_refresh = data.get("force_refresh", False)
        
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        
        # Cek cache terlebih dahulu (jika tidak force refresh)
        if not force_refresh:
            cached_result = billing_db.get_license_cache(email, max_age_hours=1)
            if cached_result:
                log_request("license_validate", {"email": email}, "cache_hit")
                return {
                    **cached_result,
                    "last_check": datetime.now().isoformat()
                }
        
        # Fresh validation - cek dari subscription_status.json lokal
        subscription_file = Path("config/subscription_status.json")
        if subscription_file.exists():
            try:
                with open(subscription_file, 'r', encoding='utf-8') as f:
                    sub_data = json.load(f)
                
                # Validasi email match
                sub_email = sub_data.get("email", "").lower()
                if sub_email == email or sub_email == email.split('@')[0]:  # Handle both formats
                    is_valid = sub_data.get("status") == "paid"
                    tier = sub_data.get("package", "basic")
                    expire_date = sub_data.get("expire_date")
                    daily_usage = sub_data.get("usage_stats", {})
                    
                    # Update cache di database
                    license_data = {
                        "is_valid": is_valid,
                        "tier": tier,
                        "expire_date": expire_date,
                        "daily_usage": daily_usage
                    }
                    billing_db.set_license_cache(email, license_data)
                    
                    log_request("license_validate", {"email": email}, f"valid: {is_valid}, tier: {tier}")
                    
                    return {
                        "is_valid": is_valid,
                        "tier": tier,
                        "expire_date": expire_date,
                        "daily_usage": daily_usage,
                        "last_check": datetime.now().isoformat(),
                        "cached": False
                    }
            except Exception as e:
                print(f"Error reading subscription file: {e}")
        
        # Default response jika tidak ada subscription yang valid
        log_request("license_validate", {"email": email}, "invalid")
        
        return {
            "is_valid": False,
            "tier": "demo",
            "expire_date": None,
            "daily_usage": {},
            "last_check": datetime.now().isoformat(),
            "cached": False
        }
        
    except Exception as e:
        log_error("license_validate", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/email/track")
async def track_email_activity(request: Request):
    """
    Track email login/logout activity.
    Request: {"email": "user@example.com", "action": "login"|"logout"}
    Response: {"success": true, "login_count": 5}
    """
    try:
        data = await request.json()
        email = data.get("email", "").strip().lower()
        action = data.get("action", "").lower()
        
        if not email or action not in ["login", "logout"]:
            raise HTTPException(status_code=400, detail="Valid email and action (login/logout) required")
        
        result = billing_db.track_email_activity(email, action)
        log_request("email_track", {"email": email, "action": action}, f"count: {result['login_count']}")
        
        return {
            "success": True,
            "email": email,
            "action": action,
            "login_count": result["login_count"],
            "timestamp": result["timestamp"]
        }
        
    except Exception as e:
        log_error("email_track", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/email/last_logout")
async def get_last_logout_email():
    """
    Get email yang terakhir logout (untuk compatibility dengan sistem lama).
    Response: {"email": "user@example.com"} atau {"email": null}
    """
    try:
        last_email = billing_db.get_last_logout_email()
        
        return {
            "success": True,
            "email": last_email
        }
        
    except Exception as e:
        log_error("last_logout", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})

# ========== ADMIN/DEBUG ENDPOINTS ==========

@app.get("/api/admin/stats")
async def get_admin_stats():
    """Get admin statistics untuk monitoring."""
    try:
        stats = billing_db.get_admin_stats()
        return stats
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "StreamMate AI Server",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

# ========== STARTUP MESSAGE ==========
@app.on_event("startup")
async def startup_event():
    print("=" * 60)
    print("🚀 STREAMMATE AI SERVER STARTED")
    print("=" * 60)
    print("📊 Billing Security: ENABLED")
    print("🗄️  Database: billing_security.db")
    print("🔐 Demo Protection: ACTIVE")
    print("⏱️  Session Tracking: ACTIVE")
    print("📧 Email Tracking: ACTIVE")
    print("💾 License Cache: ACTIVE")
    print("=" * 60)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)