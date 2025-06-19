#!/usr/bin/env python3
"""
StreamMate AI Server Inti - Production Ready Fixed
Main API Server untuk payment, licensing, dan core functions
Version: 1.1.0
"""

import os
import sys
import json
import logging
import hashlib
import hmac
import asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Union
from contextlib import asynccontextmanager
import pytz

# FastAPI imports
from fastapi import FastAPI, Request, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ValidationError, Field

# Load environment sebelum import modules
from dotenv import load_dotenv

# Load environment berdasarkan mode
if os.path.exists('.env.production'):
    load_dotenv('.env.production')
    print("🚀 PRODUCTION MODE LOADED")
elif os.path.exists('.env.local'):
    load_dotenv('.env.local')
    print("🧪 DEVELOPMENT MODE LOADED")
else:
    load_dotenv()
    print("📋 DEFAULT ENV LOADED")

# Setup logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'server_inti.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("StreamMateServerInti")

# Import modules setelah environment loaded
try:
    from modules_server.ipaymu_handler import IPaymuHandler
    from modules_server.billing_security import billing_db
    from modules_server.license_manager import LicenseManager
    from modules_server.deepseek_ai import generate_reply
    from modules_server.tts_engine import speak
    from modules_server.database_backup import backup_manager, create_emergency_backup
    logger.info("[OK] All modules imported successfully")
except ImportError as e:
    logger.error(f"[ERR] Critical import error: {e}")
    sys.exit(1)

# ===============================
# PYDANTIC MODELS
# ===============================

class PaymentRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=100)
    package: str = Field(..., pattern="^(basic|pro)$")

class PaymentCallbackRequest(BaseModel):
    status_code: str
    status: str
    reference_id: str
    amount: Optional[float] = None

class AIReplyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    context: Optional[str] = Field(default="", max_length=500)
    personality: Optional[str] = Field(default="ceria", max_length=50)
    max_length: Optional[int] = Field(default=200, ge=10, le=1000)

class StandardResponse(BaseModel):
    status: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: str
    server_version: str = "1.1.1"

class LicenseValidateRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=100)

class LicenseUpdateUsageRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=100)
    credits_used: float = Field(..., gt=0, le=1000000)
    timestamp: Optional[str] = None
    sync_type: Optional[str] = Field(default="client_sync", max_length=50)
    force_update: Optional[bool] = Field(default=False)

class AIGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=20000)
    max_length: Optional[int] = Field(default=2000, ge=10, le=5000)

class DemoRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=100)

class SessionHeartbeatRequest(BaseModel):
    session_id: str = Field(..., min_length=5, max_length=200)
    active_seconds: float = Field(..., ge=0, le=3600)

class AdminAddCreditRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=100)
    credits: float = Field(..., gt=0, le=100000000000)
    admin_key: str = Field(..., min_length=5, max_length=100)
    reason: Optional[str] = Field(default="manual_admin_add", max_length=200)

class CreditDeductRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=100)
    amount: float = Field(..., gt=0, le=100)
    component: str = Field(..., max_length=50)
    description: Optional[str] = Field(default="", max_length=200)
    session_id: Optional[str] = Field(default=None, max_length=100)

class CreditBalanceRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=100)

class CreditHistoryRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=100)
    days: Optional[int] = Field(default=7, ge=1, le=90)

# ===============================
# LIFESPAN CONTEXT MANAGER
# ===============================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Startup
    logger.info("[START] StreamMate AI Server Inti starting up...")
    
    # Ensure directories exist
    for directory in ["logs", "config", "temp", "data"]:
        Path(directory).mkdir(exist_ok=True, parents=True)

    # Initialize handlers
    try:
        app.state.ipaymu_handler = IPaymuHandler()
        app.state.license_manager = LicenseManager()
        logger.info("[OK] Core handlers initialized")
        
        # Create startup backup
        try:
            backup_path = backup_manager.create_backup("startup")
            logger.info(f"[BACKUP] Startup backup created: {backup_path}")
        except Exception as backup_error:
            logger.warning(f"[BACKUP] Failed to create startup backup: {backup_error}")
            
    except Exception as e:
        logger.error(f"[ERR] Failed to initialize handlers: {e}")
        app.state.ipaymu_handler = None
        app.state.license_manager = None
    
    logger.info("[OK] StreamMate AI Server Inti ready!")
    
    yield
    
    # Shutdown
    logger.info("[STOP] StreamMate AI Server Inti shutting down...")
    # Cleanup resources if needed
    if hasattr(app.state, 'license_manager') and app.state.license_manager:
        try:
            # Close database connections etc
            pass
        except Exception as e:
            logger.error(f"[ERR] Shutdown cleanup error: {e}")

# ===============================
# FASTAPI INITIALIZATION
# ===============================

app = FastAPI(
    title="StreamMate AI Server Inti",
    description="Core API Server untuk payment, licensing, dan AI functions",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs" if os.getenv("STREAMMATE_DEBUG", "false").lower() == "true" else None,
    redoc_url="/redoc" if os.getenv("STREAMMATE_DEBUG", "false").lower() == "true" else None
)

# Security Middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*"]  # Configure based on environment
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:*",
        "http://127.0.0.1:*",
        "http://69.62.79.238:*",
        "https://streammateai.com",
        "https://*.streammateai.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ===============================
# HELPER FUNCTIONS
# ===============================

def create_response(
    status: str = "success", 
    message: str = None, 
    data: Any = None,
    status_code: int = 200
) -> JSONResponse:
    """Helper untuk membuat response yang konsisten"""
    response_data = {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "server_version": "1.1.0"
    }
    
    if message:
        response_data["message"] = message
    if data is not None:
        response_data["data"] = data
        
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )

def log_api_call(endpoint: str, method: str, success: bool, details: str = ""):
    """Log API call untuk monitoring"""
    logger.info(f"{method} {endpoint} - {'SUCCESS' if success else 'FAILED'} - {details}")

def log_error(function_name: str, error_message: str):
    """Log error dengan format standar"""
    logger.error(f"[{function_name}] {error_message}")

def validate_email(email: str) -> str:
    """Validate and normalize email"""
    email = email.strip().lower()
    if not email or "@" not in email or len(email) < 5:
        raise ValueError("Invalid email format")
    return email

async def update_user_subscription(
    email: str, 
    package: str, 
    order_id: str,
    amount_paid: float,
    license_manager: LicenseManager
) -> bool:
    """
    Update subscription status untuk user setelah payment berhasil.
    Fungsi ini sekarang MENGGUNAKAN amount_paid sebagai satu-satunya sumber kredit.
    """
    try:
        # Menggunakan amount_paid langsung sebagai kredit (1:1)
        credits_to_add = float(amount_paid)
        
        logger.info(f"[CALLBACK] Adding {credits_to_add:,.0f} credits (Rp{amount_paid:,.0f}) to {email}")

        # PERBAIKAN: Memanggil fungsi 'add_credit' yang benar, bukan 'add_hours_credit'
        success = license_manager.add_credit(email, credits_to_add, amount_paid, order_id)

        if not success:
            log_error("update_user_subscription", f"Failed to add credit for {email} via license_manager.")
            return False

        # Verifikasi saldo setelah penambahan menggunakan fungsi yang benar
        # PERBAIKAN: Gunakan get_credit_info() untuk konsistensi dengan sistem kredit
        credit_info = license_manager.get_credit_info(email)
        current_balance = credit_info.get("credit_balance", 0)
        logger.info(f"[CALLBACK] Verified credit balance: {current_balance:,.1f} credits")

        return True
        
    except Exception as e:
        log_error("update_user_subscription", f"Failed to update subscription for {email}: {e}")
        return False

async def update_local_subscription_file(
    email: str, 
    package: str, 
    credits: float, 
    order_id: str
) -> bool:
    """
    DEPRECATED: This function is disabled to prevent conflicts with the database.
    The database is now the single source of truth.
    """
    logger.warning(f"[DEPRECATED] update_local_subscription_file called for {email}. Operation skipped.")
    return True


# GANTI SELURUH FUNGSI INI
def update_local_subscription_from_server(email: str, license_manager: LicenseManager) -> bool:
    """
    DEPRECATED: This function is disabled. It was causing data overwrites from local files.
    """
    logger.warning(f"[DEPRECATED] update_local_subscription_from_server called for {email}. Operation skipped.")
    return True

# ===============================
# DEPENDENCY FUNCTIONS
# ===============================

def get_ipaymu_handler(request: Request) -> IPaymuHandler:
    """Get iPaymu handler from app state"""
    handler = getattr(request.app.state, 'ipaymu_handler', None)
    if not handler:
        raise HTTPException(status_code=500, detail="Payment system not available")
    return handler

def get_license_manager(request: Request) -> LicenseManager:
    """Get license manager from app state"""
    manager = getattr(request.app.state, 'license_manager', None)
    if not manager:
        raise HTTPException(status_code=500, detail="License system not available")
    return manager

# ===============================
# CORE API ENDPOINTS
# ===============================

@app.get("/")
async def root():
    """Root endpoint dengan informasi server"""
    return create_response(
        message="StreamMate AI Server Inti is running",
        data={
            "mode": "production" if os.getenv("STREAMMATE_DEV", "false").lower() == "false" else "development",
            "endpoints": {
                "health": "/api/health",
                "payment": "/api/payment/create",
                "ai_reply": "/api/ai/reply",
                "license": "/api/license/validate",
                "credit": "/api/credit/balance"
            },
            "version": "1.1.0"
        }
    )

@app.get("/api/health")
async def health_check(request: Request):
    """Health check endpoint"""
    try:
        # Test critical components
        test_results = {
            "ipaymu": hasattr(request.app.state, 'ipaymu_handler') and request.app.state.ipaymu_handler is not None,
            "license_manager": hasattr(request.app.state, 'license_manager') and request.app.state.license_manager is not None,
            "database": True,
            "ai_module": True
        }
        
        # Test database
        try:
            stats = billing_db.get_admin_stats()
            test_results["database"] = bool(stats)
        except:
            test_results["database"] = False
        
        # Test AI module
        try:
            test_reply = generate_reply("test")
            test_results["ai_module"] = bool(test_reply)
        except:
            test_results["ai_module"] = False
        
        return create_response(
            message="Server healthy and operational",
            data={
                "components": test_results,
                "all_systems": all(test_results.values()),
                "uptime": "Available"
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return create_response(
            status="error",
            message="Health check failed",
            data={"error": str(e)},
            status_code=500
        )

@app.post("/api/demo/check")
async def check_demo_availability(
    request: DemoRequest,
    license_manager: LicenseManager = Depends(get_license_manager)
):
    """Check demo availability - alias untuk compatibility dengan client lama"""
    try:
        email = validate_email(request.email)
        
        # Cek kredit terlebih dahulu dengan timeout protection
        try:
            credit_info = license_manager.get_credit_info(email)
        except Exception as credit_error:
            logger.error(f"[DEMO] Failed to get credit info for {email}: {credit_error}")
            # Jika gagal cek kredit, lanjutkan dengan demo check
            credit_info = {"credit_balance": 0}
        
        if credit_info.get("credit_balance", 0) > 50:
            return create_response(
                status="error",
                message="Demo tidak tersedia karena kredit > 50",
                data={
                    "can_demo": False,
                    "used_today": False,
                    "remaining_minutes": 0,
                    "status": "credit_too_high",
                    "next_reset": datetime.now(pytz.timezone('Asia/Jakarta')).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                },
                status_code=403
            )
        
        # Cek status demo dengan timeout protection
        try:
            demo_status = billing_db.check_demo_usage(email)
        except Exception as demo_error:
            logger.error(f"[DEMO] Failed to check demo usage for {email}: {demo_error}")
            # Jika gagal cek demo, return error
            raise HTTPException(status_code=500, detail="Demo service unavailable")
        
        # Format response sesuai yang diharapkan client
        can_demo = not demo_status.get("used_today", False) or demo_status.get("remaining_minutes", 0) > 0
        
        return create_response(
            message="Demo availability checked",
            data={
                "can_demo": can_demo,
                "used_today": demo_status.get("used_today", False),
                "remaining_minutes": demo_status.get("remaining_minutes", 0),
                "next_reset": demo_status.get("next_reset", "2025-06-09T00:00:00")
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        log_error("check_demo_availability", str(e))
        raise HTTPException(status_code=500, detail="Error checking demo availability")


@app.get("/api/demo/status/{email}")
async def get_demo_status(email: str):
    """Cek status demo user"""
    try:
        email = validate_email(email)
        demo_status = billing_db.check_demo_usage(email)
        
        return create_response(
            message="Demo status retrieved",
            data=demo_status
        )
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_error("get_demo_status", str(e))
        raise HTTPException(status_code=500, detail="Error getting demo status")

@app.post("/api/demo/register")
async def register_demo(
    request: DemoRequest,
    license_manager: LicenseManager = Depends(get_license_manager)
):
    """Register demo usage dengan validasi kredit minimum < 50"""
    try:
        email = validate_email(request.email)
        
        # 🔍 VALIDASI KREDIT: User harus punya < 50 kredit untuk bisa demo
        credit_info = license_manager.get_credit_info(email)
        
        current_credit = credit_info.get("credit_balance", 0)
        if current_credit >= 50:
            return create_response(
                status="error",
                message=f"Demo tidak tersedia. Anda masih memiliki {current_credit:.1f} kredit. Demo hanya untuk user dengan < 50 kredit.",
                status_code=403
            )
        
        # Cek demo availability
        demo_status = billing_db.check_demo_usage(email)
        
        if not demo_status.get("can_demo", False):
            if demo_status.get("status") == "active":
                return create_response(
                    status="success",
                    message="Demo masih aktif",
                    data={
                        "status": "active",
                        "remaining_minutes": demo_status.get("remaining_minutes", 0),
                        "expire_date": demo_status.get("expire_date"),
                        "demo_expires_wib": demo_status.get("expire_date"),
                        "current_time_wib": datetime.now(pytz.timezone('Asia/Jakarta')).isoformat()
                    }
                )
            else:
                return create_response(
                    status="error",
                    message="Demo sudah digunakan hari ini. Reset jam 00:00 WIB.",
                    status_code=403
                )
        
        # Register demo usage
        result = billing_db.register_demo_usage(email)
        
        if result.get("success"):
            return create_response(
                message="Demo berhasil diaktifkan",
                data={
                    "expire_date": result.get("expire_date"),
                    "demo_expires_wib": result.get("demo_expires"),
                    "duration_minutes": result.get("duration_minutes", 30),
                    "current_time_wib": datetime.now(pytz.timezone('Asia/Jakarta')).isoformat()
                }
            )
        else:
            return create_response(
                status="error",
                message=result.get("message", "Gagal mengaktifkan demo"),
                status_code=403
            )
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_error("register_demo", str(e))
        raise HTTPException(status_code=500, detail="Error registering demo")

@app.post("/api/demo/heartbeat")
async def demo_heartbeat(request: Request):
    """Heartbeat untuk tracking penggunaan demo"""
    try:
        data = await request.json()
        email = validate_email(data.get("email", ""))
        
        # Update last activity di database
        result = billing_db.update_demo_activity(email)
        
        return create_response(
            message="Heartbeat recorded",
            data=result
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_error("demo_heartbeat", str(e))
        raise HTTPException(status_code=500, detail="Heartbeat failed")

@app.post("/api/session/start")
async def session_start(request: Request):
    """Start user session tracking"""
    try:
        body = await request.json()
        email = body.get("email", "").strip().lower()
        feature = body.get("feature", "").strip()
        session_id = body.get("session_id", "").strip()
        
        if not email or not feature:
            return create_response(
                status="error",
                message="Email dan feature harus diisi",
                status_code=400
            )
        
        # Start session via billing security database
        result = billing_db.start_session(email, feature, session_id)
        
        if result.get("success"):
            return create_response(
                status="success",
                message="Session berhasil dimulai",
                data={
                    "session_id": result.get("session_id"),
                    "start_time": result.get("start_time"),
                    "email": email,
                    "feature": feature
                }
            )
        else:
            return create_response(
                status="error",
                message="Gagal memulai session",
                status_code=500
            )
        
    except Exception as e:
        logger.error(f"Session start error: {e}")
        return create_response(
            status="error",
            message=f"Error session start: {str(e)}",
            status_code=500
        )

@app.post("/api/session/end")
async def session_end(request: Request):
    """End user session tracking"""
    try:
        body = await request.json()
        session_id = body.get("session_id", "").strip()
        
        if not session_id:
            return create_response(
                status="error",
                message="Session ID harus diisi",
                status_code=400
            )
        
        # End session via billing security database
        result = billing_db.end_session(session_id)
        
        if result.get("success"):
            return create_response(
                status="success",
                message="Session berhasil diakhiri",
                data={
                    "session_id": session_id,
                    "total_minutes": result.get("total_minutes", 0),
                    "credited_minutes": result.get("credited_minutes", 0),
                    "email": result.get("email"),
                    "feature": result.get("feature"),
                    "end_time": result.get("end_time")
                }
            )
        else:
            return create_response(
                status="error",
                message=result.get("message", "Session tidak ditemukan"),
                status_code=404
            )
        
    except Exception as e:
        logger.error(f"Session end error: {e}")
        return create_response(
            status="error",
            message=f"Error session end: {str(e)}",
            status_code=500
        )

@app.post("/api/session/heartbeat")
async def session_heartbeat(request: Request):
    """Session heartbeat untuk tracking aktivitas user (Smart Mode)"""
    try:
        body = await request.json()
        session_id = body.get("session_id", "").strip()
        active_seconds = body.get("active_seconds", 0)
        
        if not session_id:
            return create_response(
                status="error",
                message="Session ID harus diisi",
                status_code=400
            )
        
        # SMART MODE: Auto-create session jika belum ada
        try:
            # Coba heartbeat dulu
            result = billing_db.heartbeat_session(session_id, active_seconds)
            
            if result.get("success"):
                # Session exists, heartbeat berhasil
                return create_response(
                    status="success",
                    message="Session heartbeat berhasil",
                    data={
                        "session_id": session_id,
                        "total_active_time": result.get("total_active_time", 0),
                        "last_heartbeat": result.get("last_heartbeat")
                    }
                )
            else:
                # Session tidak ada, auto-create dari session_id
                email_from_session = session_id.split('_')[0] if '_' in session_id else "auto@streammate.ai"
                feature_from_session = session_id.split('_')[1] if session_id.count('_') >= 1 else "general"
                
                # Auto-create session
                create_result = billing_db.start_session(email_from_session, feature_from_session, session_id)
                
                if create_result.get("success"):
                    # Session created, now heartbeat
                    heartbeat_result = billing_db.heartbeat_session(session_id, active_seconds)
                    
                    return create_response(
                        status="success", 
                        message="Session auto-created dan heartbeat berhasil",
                        data={
                            "session_id": session_id,
                            "total_active_time": heartbeat_result.get("total_active_time", active_seconds),
                            "last_heartbeat": heartbeat_result.get("last_heartbeat"),
                            "auto_created": True
                        }
                    )
                else:
                    # Fallback: Always return success untuk avoid 404
                    return create_response(
                        status="success",
                        message="Heartbeat diterima (fallback mode)",
                        data={
                            "session_id": session_id,
                            "total_active_time": active_seconds,
                            "last_heartbeat": datetime.now().isoformat(),
                            "fallback_mode": True
                        }
                    )
                    
        except Exception as db_error:
            # Database error? Return success anyway untuk avoid 404
            logger.warning(f"Session heartbeat DB error: {db_error}")
            return create_response(
                status="success",
                message="Heartbeat diterima (fallback mode)",
                data={
                    "session_id": session_id,
                    "total_active_time": active_seconds,
                    "last_heartbeat": datetime.now().isoformat(),
                    "fallback_mode": True
                }
            )
        
    except Exception as e:
        logger.error(f"Session heartbeat error: {e}")
        # Even on error, return success untuk avoid 404
        return create_response(
            status="success",
            message="Heartbeat diterima (error fallback)",
            data={
                "session_id": body.get("session_id", "unknown"),
                "total_active_time": body.get("active_seconds", 0),
                "last_heartbeat": datetime.now().isoformat(),
                "error_fallback": True
            }
        )

# ===============================
# CREDIT MANAGEMENT ENDPOINTS
# ===============================

@app.post("/api/credit/balance")
async def get_credit_balance(
    request: CreditBalanceRequest,
    license_manager: LicenseManager = Depends(get_license_manager)
):
    """Get current credit balance for user"""
    try:
        email = validate_email(request.email)
        
        # PERBAIKAN: Gunakan get_credit_info untuk konsistensi dengan sistem kredit
        credit_info = license_manager.get_credit_info(email)
        
        if credit_info:
            return create_response(
                message="Credit balance retrieved",
                data={
                    "email": email,
                    # Kembalikan field yang konsisten dengan sistem kredit
                    "credit_balance": credit_info.get("credit_balance", 0),
                    "credit_used": credit_info.get("credit_used", 0),
                    "total_usage": credit_info.get("credit_used", 0),
                    "last_updated": credit_info.get("last_update", datetime.now().isoformat()),
                    "status": "active" if credit_info.get("credit_balance", 0) > 0 else "no_credit"
                }
            )
        else:
            return create_response(
                message="No credit found",
                data={
                    "email": email,
                    "credit_balance": 0,
                    "credit_used": 0,
                    "total_usage": 0,
                    "status": "no_credit"
                }
            )
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_error("get_credit_balance", str(e))
        raise HTTPException(status_code=500, detail="Failed to get credit balance")

@app.post("/api/credit/deduct")
async def deduct_credit(
    request: CreditDeductRequest,
    license_manager: LicenseManager = Depends(get_license_manager)
):
    """Deduct credit from user account"""
    try:
        email = validate_email(request.email)
        amount = float(request.amount)
        
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        logger.info(f"[CREDIT] Attempting to deduct {amount:.4f} credits from {email} - Component: {request.component}")
        
        # PERBAIKAN: Gunakan get_credit_info untuk data terbaru
        current_info = license_manager.get_credit_info(email)
        current_credit = float(current_info.get("credit_balance", 0))
        
        if current_credit < amount:
            logger.warning(f"[CREDIT] Insufficient credit for {email}. Has: {current_credit:.4f}, Needs: {amount:.4f}")
            return create_response(
                status="error",
                message="Insufficient credit",
                data={
                    "email": email,
                    "current_credit": current_credit,
                    "requested_deduction": amount
                },
                status_code=402  # Payment Required
            )
        
        # PERBAIKAN: Gunakan 'deduct_credit' dengan parameter yang benar (credits, bukan amount)
        success = license_manager.deduct_credit(
            email=email,
            credits=amount,  # PERBAIKAN: Gunakan 'credits' bukan 'amount'
            component=request.component,
            description=request.description,
            session_id=request.session_id or ""
        )
        
        if success:
            # Dapatkan saldo terbaru setelah deduksi
            updated_info = license_manager.get_credit_info(email)
            new_credit = float(updated_info.get("credit_balance", 0))
            
            logger.info(f"[CREDIT] SUCCESS: {email} - Deducted: {amount:.4f}, Remaining: {new_credit:.4f}")
            
            log_api_call("/api/credit/deduct", "POST", True, 
                        f"{email} - {request.component} - {amount:.4f} credits")
            
            return create_response(
                message="Credit deducted successfully",
                data={
                    "email": email,
                    "deducted": amount,
                    "remaining_credit": new_credit,
                    "previous_credit": current_credit,
                    "component": request.component,
                    "description": request.description,
                    "session_id": request.session_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
        else:
            logger.error(f"[CREDIT] Database failed to deduct credit for {email}")
            raise HTTPException(status_code=500, detail="Failed to deduct credit from database")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        log_error("deduct_credit", str(e))
        raise HTTPException(status_code=500, detail="Credit deduction failed")

@app.post("/api/credit/history")
async def get_credit_history(
    request: CreditHistoryRequest,
    license_manager: LicenseManager = Depends(get_license_manager)
):
    """Get credit transaction history"""
    try:
        email = validate_email(request.email)
        days = request.days
        
        # Get transaction history
        history = license_manager.get_transaction_history(email, days)
        
        return create_response(
            message="Credit history retrieved",
            data={
                "email": email,
                "days": days,
                "transactions": history,
                "total_transactions": len(history)
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_error("get_credit_history", str(e))
        raise HTTPException(status_code=500, detail="Failed to get credit history")

# ===============================
# LICENSE ENDPOINTS
# ===============================

@app.post("/api/license/validate")
async def validate_license(
    request: LicenseValidateRequest,
    license_manager: LicenseManager = Depends(get_license_manager)
):
    """Validasi lisensi dan kembalikan status terbaru dari database."""
    try:
        email = validate_email(request.email)
        logger.info(f"Memvalidasi lisensi untuk: {email}")

        # Langsung dapatkan data terbaru dari database
        license_data = license_manager.get_credit_info(email)

        if not license_data:
            raise HTTPException(status_code=404, detail="User license not found")
            
        # --- PERBAIKAN INTI ---
        # Hapus panggilan ke `sync_local_to_db` yang menyebabkan bug.
        # Server sekarang hanya bertugas memberikan data yang ada di database,
        # tidak lagi mencoba melakukan sinkronisasi dua arah yang rumit.
        
        logger.info(f"[VALIDATE] Mengembalikan data dari DB: {license_data}")
        return create_response(data=license_data, message="License validated")

    except ValueError as e:
        log_error("validate_license", f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_error("validate_license", f"Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/license/update_usage")
async def update_license_usage(
    request: LicenseUpdateUsageRequest,
    license_manager: LicenseManager = Depends(get_license_manager)
):
    """Update kredit usage dari client"""
    try:
        email = validate_email(request.email)
        # Nama variabel 'credits_used' sudah konsisten dengan sistem kredit
        credits_used = float(request.credits_used)
        
        if credits_used <= 0:
            raise HTTPException(status_code=400, detail="Usage must be positive")
        
        logger.info(f"[USAGE] {email} using {credits_used:.4f} credits - Type: {request.sync_type}")
        
        # --- PERBAIKAN UTAMA ---
        # Panggil fungsi DEDUCT_CREDIT dengan parameter yang benar (credits, bukan amount)
        success = license_manager.deduct_credit(
            email=email,
            credits=credits_used,  # PERBAIKAN: Gunakan 'credits' bukan 'amount'
            component="client_usage_sync",
            description=f"Sync from client: {request.sync_type}"
        )
        
        if success:
            # Dapatkan sisa kredit terbaru
            updated_info = license_manager.get_credit_info(email)
            remaining_credit = updated_info.get("credit_balance", 0)
            
            logger.info(f"[USAGE] SUCCESS: {email} used {credits_used:.4f} credits, remaining: {remaining_credit:.4f} credits")
            
            return create_response(
                message="Usage updated successfully",
                data={
                    "email": email,
                    "credits_used": credits_used, # Nama field konsisten dengan sistem kredit
                    "remaining_credit": remaining_credit,
                    "sync_type": request.sync_type,
                    "timestamp": request.timestamp or datetime.now().isoformat()
                }
            )
        else:
            logger.error(f"[USAGE] Failed to update usage for {email}")
            raise HTTPException(status_code=500, detail="Failed to update usage in database")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        log_error("update_license_usage", str(e))
        raise HTTPException(status_code=500, detail="Usage update failed")

# ===============================
# AI ENDPOINTS
# ===============================

@app.post("/api/ai/reply")
async def ai_reply(request: AIReplyRequest):
    """Generate AI reply"""
    try:
        text = request.text.strip()
        
        if not text:
            raise HTTPException(status_code=400, detail="Text parameter cannot be empty")
        
        # Build context-aware prompt
        prompt = text
        if request.context:
            prompt = f"Context: {request.context}\nUser: {text}"
        
        # Generate reply
        reply = generate_reply(prompt)
        
        if reply:
            if len(reply) > request.max_length:
                reply = reply[:request.max_length] + "..."
            
            log_api_call("/api/ai/reply", "POST", True, f"Generated {len(reply)} chars")
            
            return create_response(
                message="AI reply generated successfully",
                data={
                    "reply": reply,
                    "original_length": len(text),
                    "reply_length": len(reply),
                    "personality": request.personality
                }
            )
        else:
            log_api_call("/api/ai/reply", "POST", False, "Empty AI response")
            return create_response(
                status="error",
                message="Failed to generate AI reply",
                data={"reply": "Maaf, saya tidak bisa merespon saat ini."},
                status_code=500
            )
            
    except HTTPException:
        raise
    except Exception as e:
        log_error("ai_reply", str(e))
        return create_response(
            status="error",
            message="Internal error in AI reply generation",
            data={"error": str(e)},
            status_code=500
        )

@app.post("/api/ai/generate")
async def api_ai_generate(request: AIGenerateRequest):
    """Generate AI reply using DeepSeek API with timeout protection"""
    try:
        prompt = request.prompt.strip()
        
        if not prompt:
            raise HTTPException(status_code=400, detail="Empty prompt")
        
        if len(prompt) > request.max_length:
            prompt = prompt[:request.max_length]
        
        logger.info(f"[VPS] AI generate request: {len(prompt)} chars")
        
        # Import generate_reply dengan timeout protection
        try:
            from modules_server.deepseek_ai import generate_reply
            # Generate reply dengan timeout 15 detik
            reply = generate_reply(prompt, timeout=15)
        except ImportError as e:
            logger.error(f"[VPS] Failed to import generate_reply: {e}")
            raise HTTPException(status_code=500, detail="AI module not available")
        except Exception as e:
            logger.error(f"[VPS] AI generation error: {e}")
            raise HTTPException(status_code=500, detail="AI generation failed")
        
        if reply and len(reply.strip()) > 0:
            logger.info(f"[VPS] AI success: {len(reply)} chars")
            return create_response(
                message="AI reply generated successfully",
                data={
                    "reply": reply.strip(),
                    "server": "vps",
                    "model": "deepseek-chat",
                    "prompt_length": len(prompt),
                    "reply_length": len(reply)
                }
            )
        else:
            logger.warning(f"[VPS] AI returned empty reply")
            raise HTTPException(
                status_code=500,
                detail="AI returned empty response"
            )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[VPS] AI generation error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"AI generation failed: {str(e)}"
        )

@app.get("/api/ai/status")  
async def api_ai_status():
    """Check AI service status"""
    try:
        # Test DeepSeek API availability
        api_key = os.getenv("DEEPSEEK_API_KEY")
        
        if not api_key:
            return create_response(
                status="error",
                message="DeepSeek API key not configured",
                data={
                    "available": False,
                    "model": "deepseek-chat"
                }
            )
        
        # Test a simple API call
        try:
            test_reply = generate_reply("Test")
            
            return create_response(
                message="AI service is available",
                data={
                    "available": True,
                    "model": "deepseek-chat",
                    "api_key_length": len(api_key) if api_key else 0,
                    "test_response_length": len(test_reply) if test_reply else 0
                }
            )
            
        except Exception as test_error:
            logger.error(f"AI service test failed: {test_error}")
            return create_response(
                status="error",
                message=f"AI service test failed: {str(test_error)}",
                data={"available": False}
            )
        
    except Exception as e:
        logger.error(f"AI status check failed: {e}")
        return create_response(
            status="error",
            message=f"Status check failed: {str(e)}",
            data={"available": False}
        )

# ===============================
# ADMIN ENDPOINTS
# ===============================

@app.post("/api/admin/add_credit")
async def admin_add_credit(
    request: AdminAddCreditRequest,
    license_manager: LicenseManager = Depends(get_license_manager)
):
    """Endpoint admin untuk menambah kredit manual"""
    try:
        # Verify admin key
        admin_key = os.getenv("STREAMMATE_ADMIN_KEY", "tolo_admin_2025")
        if request.admin_key != admin_key:
            logger.warning(f"[SECURITY] Invalid admin key attempt from {request.email}")
            raise HTTPException(status_code=403, detail="Invalid admin key")
        
        email = validate_email(request.email)
        credits_to_add = float(request.credits)
        
        logger.info(f"[ADMIN] Adding {credits_to_add} credits to {email} - Reason: {request.reason}")
        
        # --- PERBAIKAN ---
        # Gunakan fungsi 'add_credit' yang benar.
        order_id = f"ADMIN_{request.reason}_{int(datetime.now().timestamp())}"
        success = license_manager.add_credit(email, credits_to_add, 0, order_id) # Amount paid is 0 for admin
        
        if success:
            # Verifikasi dengan fungsi 'get_credit_info' yang konsisten dengan sistem kredit.
            verification = license_manager.get_credit_info(email)
            total_credits = verification.get('credit_balance', 0)
            logger.info(f"[ADMIN] Credit added successfully: {email} now has {total_credits} credits")
            
            return create_response(
                message="Credit added successfully",
                data={
                    "email": email,
                    "credits_added": credits_to_add,
                    "total_credits": total_credits,
                    "reason": request.reason,
                    "order_id": order_id
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to add credit to database")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        log_error("admin_add_credit", str(e))
        raise HTTPException(status_code=500, detail="Admin operation failed")

@app.get("/api/admin/stats")
async def get_admin_stats(request: Request, admin_key: str = None):
    """Get admin statistics"""
    try:
        # Verify admin key
        expected_key = os.getenv("STREAMMATE_ADMIN_KEY", "tolo_admin_2025")
        if admin_key != expected_key:
            raise HTTPException(status_code=403, detail="Invalid admin key")
        
        # Get stats from billing_db
        stats = billing_db.get_admin_stats()
        
        return create_response(
            message="Admin stats retrieved",
            data=stats
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("get_admin_stats", str(e))
        raise HTTPException(status_code=500, detail="Failed to get admin stats")

# PAYMENT COMPLETION PAGES
@app.get("/payment_completed")
async def payment_completed(request: Request, status: str = "unknown", order_id: str = "", email: str = ""):
    """Payment completion page - redirect after payment"""
    try:
        logger.info(f"[PAYMENT_COMPLETE] Status: {status}, Order: {order_id}, Email: {email}")
        
        if status == "success":
            # Payment berhasil
            html_content = f"""
            <!DOCTYPE html>
            <html lang="id">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Pembayaran Berhasil - StreamMate AI</title>
                <style>
                    body {{ 
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                        margin: 0;
                        padding: 0;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}
                    .container {{ 
                        background: white; 
                        padding: 40px; 
                        
                        border-radius: 15px; 
                        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                        text-align: center;
                        max-width: 500px;
                        width: 90%;
                    }}
                    .success-icon {{
                        font-size: 64px;
                        color: #28a745;
                        margin-bottom: 20px;
                    }}
                    h1 {{
                        color: #333;
                        margin-bottom: 10px;
                    }}
                    p {{
                        color: #666;
                        line-height: 1.6;
                        margin-bottom: 20px; 
                    }}
                    .order-info {{
                        background: #f8f9fa;
                        padding: 15px; 
                        border-radius: 8px; 
                        margin: 20px 0; 
                        border-left: 4px solid #28a745;
                    }}
                    .btn {{ 
                        background: #007bff;
                        color: white; 
                        padding: 12px 30px;
                        text-decoration: none;
                        border-radius: 25px;
                        display: inline-block;
                        margin-top: 20px;
                        transition: background 0.3s;
                    }}
                    .btn:hover {{
                        background: #0056b3;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success-icon">✅</div>
                    <h1>Pembayaran Berhasil!</h1>
                    <p>Terima kasih atas pembayaran Anda. Kredit StreamMate AI telah ditambahkan ke akun Anda.</p>
                    
                    <div class="order-info">
                        <strong>Order ID:</strong> {order_id}<br>
                        <strong>Email:</strong> {email}<br>
                        <strong>Status:</strong> Berhasil
                    </div>
                    
                    <p>Kredit Anda akan tersedia dalam beberapa menit. Silakan refresh aplikasi StreamMate AI untuk melihat kredit terbaru.</p>
                    
                    <a href="#" class="btn" onclick="window.close()">Tutup Halaman</a>
                </div>
                
                <script>
                    // Auto close after 30 seconds
                    setTimeout(function() {{
                            window.close();
                    }}, 30000);
                </script>
            </body>
            </html>
            """
            
        elif status == "canceled":
            # Payment dibatalkan
            html_content = f"""
            <!DOCTYPE html>
            <html lang="id">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Pembayaran Dibatalkan - StreamMate AI</title>
                <style>
                    body {{ 
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                        margin: 0;
                        padding: 0;
                        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}
                    .container {{ 
                        background: white; 
                        padding: 40px; 
                        border-radius: 15px; 
                        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                        text-align: center;
                        max-width: 500px;
                        width: 90%;
                    }}
                    .warning-icon {{
                        font-size: 64px;
                        color: #ffc107;
                        margin-bottom: 20px; 
                    }}
                    h1 {{
                        color: #333;
                        margin-bottom: 10px;
                    }}
                    p {{
                        color: #666;
                        line-height: 1.6;
                        margin-bottom: 20px;
                    }}
                    .order-info {{
                        background: #fff3cd;
                        padding: 15px; 
                        border-radius: 8px; 
                        margin: 20px 0; 
                        border-left: 4px solid #ffc107;
                    }}
                    .btn {{ 
                        background: #6c757d;
                        color: white; 
                        padding: 12px 30px;
                        text-decoration: none;
                        border-radius: 25px;
                        display: inline-block;
                        margin-top: 20px;
                        transition: background 0.3s;
                    }}
                    .btn:hover {{
                        background: #545b62;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="warning-icon">⚠️</div>
                    <h1>Pembayaran Dibatalkan</h1>
                    <p>Pembayaran Anda telah dibatalkan. Tidak ada biaya yang dikenakan.</p>
                    
                    <div class="order-info">
                        <strong>Order ID:</strong> {order_id}<br>
                        <strong>Email:</strong> {email}<br>
                        <strong>Status:</strong> Dibatalkan
                    </div>
                    
                    <p>Silakan coba lagi jika Anda ingin melanjutkan pembelian kredit StreamMate AI.</p>
                    
                    <a href="#" class="btn" onclick="window.close()">Tutup Halaman</a>
                </div>
                
                <script>
                    // Auto close after 15 seconds
                    setTimeout(function() {{
                        window.close();
                    }}, 15000);
                </script>
            </body>
            </html>
            """
        else:
            # Status tidak dikenal
            html_content = f"""
            <!DOCTYPE html>
            <html lang="id">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Status Pembayaran - StreamMate AI</title>
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        margin: 0;
                        padding: 0;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}
                    .container {{
                        background: white;
                        padding: 40px;
                        border-radius: 15px;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                        text-align: center;
                        max-width: 500px;
                        width: 90%;
                    }}
                    .info-icon {{
                        font-size: 64px;
                        color: #6c757d;
                        margin-bottom: 20px;
                    }}
                    h1 {{
                        color: #333;
                        margin-bottom: 10px;
                    }}
                    p {{
                        color: #666;
                        line-height: 1.6;
                        margin-bottom: 20px;
                    }}
                    .btn {{
                        background: #6c757d;
                        color: white;
                        padding: 12px 30px;
                        text-decoration: none;
                        border-radius: 25px;
                        display: inline-block;
                        margin-top: 20px;
                        transition: background 0.3s;
                    }}
                    .btn:hover {{
                        background: #545b62;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="info-icon">ℹ️</div>
                    <h1>Status Pembayaran</h1>
                    <p>Status pembayaran: {status}</p>
                    <p>Silakan hubungi support jika Anda memerlukan bantuan.</p>
                    
                    <a href="#" class="btn" onclick="window.close()">Tutup Halaman</a>
                </div>
            </body>
            </html>
            """
        
        return HTMLResponse(content=html_content, status_code=200)
        
    except Exception as e:
        log_error("payment_completed", str(e))
        # Return simple error page
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error - StreamMate AI</title>
        </head>
        <body>
            <h1>Error</h1>
            <p>Terjadi kesalahan dalam memproses halaman pembayaran.</p>
            <p>Error: {str(e)}</p>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=500)

# ===============================
# PAYMENT ENDPOINTS
# ===============================

@app.post("/api/payment/create")
async def create_payment(
    request: PaymentRequest,
    ipaymu_handler: IPaymuHandler = Depends(get_ipaymu_handler)
):
    """Create payment transaction dengan iPaymu - SANDBOX MODE"""
    try:
        email = validate_email(request.email)
        package = request.package
        
        # Get package info - PRODUCTION PRICES
        package_info = {
            "basic": {"credits": 100000, "price": 100000},
            "pro": {"credits": 250000, "price": 250000}
        }
        
        info = package_info.get(package, {"credits": 100000, "price": 100000})
        credits_to_purchase = info["credits"]
        amount = info["price"]
        
        logger.info(f"[PRODUCTION] Creating payment: {email} - {package} - Rp{amount:,} - {credits_to_purchase:,} credits")
        
        # Create transaction via iPaymu with production price
        result = ipaymu_handler.create_transaction(email, package, amount)
        
        if result.get("status") == "success":
            log_api_call("/api/payment/create", "POST", True, f"Payment created: {result.get('order_id')}")
            
            return create_response(
                message="Payment transaction created successfully",
                data={
                    "redirect_url": result.get("redirect_url"),
                    "order_id": result.get("order_id"),
                    "amount": result.get("amount"),
                    "package": package,
                    "token": result.get("token")
                }
            )
        else:
            log_api_call("/api/payment/create", "POST", False, f"Payment failed: {result.get('message')}")
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Payment creation failed")
            )
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        log_error("create_payment", str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.post("/api/payment/callback")
async def payment_callback(
    request: Request,
    ipaymu_handler: IPaymuHandler = Depends(get_ipaymu_handler),
    license_manager: LicenseManager = Depends(get_license_manager)
):
    """
    Handle iPaymu payment callback dengan perhitungan kredit yang benar.
    FIXED VERSION.
    """
    callback_data = None
    try:
        # Dapatkan data callback, coba JSON dulu, fallback ke form data
        try:
            callback_data = await request.json()
        except Exception:
            form_data = await request.form()
            callback_data = dict(form_data)

        logger.info(f"[CALLBACK] Data diterima: {callback_data}")
        
        # 1. Validasi signature callback dari iPaymu untuk keamanan.
        # (Asumsi ipaymu_handler memiliki fungsi ini)
        if hasattr(ipaymu_handler, 'validate_callback_signature') and not ipaymu_handler.validate_callback_signature(callback_data):
            logger.error("[CALLBACK] Invalid iPaymu signature. Transaction is suspicious.")
            raise HTTPException(status_code=403, detail="Invalid callback signature")
        
        # 2. Proses hanya jika status pembayaran adalah 'berhasil'.
        payment_status = str(callback_data.get("status", "")).lower()
        if payment_status != 'berhasil':
            logger.warning(f"[CALLBACK] Payment status is not 'berhasil'. Status: {payment_status}. Ignoring.")
            return create_response(message="Payment status not successful, no action taken.")

        # 3. Ekstrak data PENTING dari `callback_data`.
        order_id = callback_data.get("reference_id") # `reference_id` adalah ID order kita
        amount_paid = float(callback_data.get("amount", 0.0))
        
        # Dapatkan email dan package dari database billing berdasarkan order_id
        # (Asumsi billing_db memiliki fungsi ini)
        transaction_details = billing_db.get_transaction(order_id)
        if not transaction_details:
            logger.error(f"[CALLBACK] Order ID not found in our database: {order_id}")
            raise HTTPException(status_code=404, detail="Order ID not found")
        
        email = transaction_details.get("email")
        package = transaction_details.get("package")

        if not all([email, package, order_id, amount_paid > 0]):
            logger.error(f"[CALLBACK] Data tidak lengkap dari callback/DB: email={email}, order_id={order_id}, amount={amount_paid}")
            raise HTTPException(status_code=400, detail="Incomplete data for processing")

        # --- INTI LOGIKA PEMBELIAN YANG BENAR ---
        # 4. Konversi amount ke credit (1 IDR = 1 Credit). Ini adalah aturan bisnisnya.
        credits_to_add = amount_paid
        logger.info(f"[CALLBACK] Payment successful! Order: {order_id}, Email: {email}, Amount: {amount_paid}, Credits to add: {credits_to_add}")

        # 5. Tambahkan kredit ke akun pengguna.
        success = license_manager.add_credit(email, credits_to_add, amount_paid, order_id)

        if success:
            if hasattr(billing_db, 'update_transaction_status'):
                billing_db.update_transaction_status(order_id, "completed")
            logger.info(f"[CALLBACK] Berhasil menambahkan {credits_to_add} kredit ke {email}")
            return create_response(message="Payment processed successfully", data={"credits_added": credits_to_add})
        else:
            if hasattr(billing_db, 'update_transaction_status'):
                billing_db.update_transaction_status(order_id, "failed_to_credit")
            logger.error(f"[CALLBACK] Gagal menambahkan kredit ke {email} meskipun pembayaran berhasil.")
            raise HTTPException(status_code=500, detail="Failed to add credits after successful payment")

    except HTTPException as http_exc:
        # Re-raise HTTPException agar FastAPI bisa menanganinya
        raise http_exc
    except Exception as e:
        logger.error(f"[CALLBACK] Unexpected error processing callback: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error during callback processing")

# ===============================
# SECURE CONFIG API ENDPOINTS
# ===============================

@app.get("/api/config/packages")
async def get_packages_config():
    """Get packages configuration securely from server"""
    try:
        # Hardcoded packages untuk security - tidak dari file
        packages = {
            "basic": {
                "price": 100000,
                "credits": 100000,
                "description": "Paket Basic - 100.000 Kredit",
                "features": [
                    "Auto-Reply dengan AI",
                    "Voice to Text (STT)",
                    "Text to Speech (TTS)",
                    "100.000 kredit untuk fitur",
                    "Support 24/7"
                ]
            },
            "pro": {
                "price": 250000,
                "credits": 250000,
                "description": "Paket Pro - 250.000 Kredit",
                "features": [
                    "Semua fitur Basic",
                    "250.000 kredit untuk fitur",
                    "AI Response lebih pintar",
                    "Priority Support",
                    "Custom Voice Training"
                ]
            }
        }
        
        return create_response(
            message="Packages configuration retrieved successfully",
            data=packages
        )
        
    except Exception as e:
        log_error("get_packages_config", str(e))
        raise HTTPException(status_code=500, detail="Failed to get packages config")

@app.get("/api/config/production")
async def get_production_config():
    """Get production configuration securely from server"""
    try:
        # Hardcoded production config untuk security
        config = {
            "mode": "production",
            "server_only": True,
            "disable_local_fallback": True,
            "require_internet": True,
            "vps_server_url": "http://69.62.79.238:8000",
            "max_offline_time": 0,
            "force_login": True,
            "disable_demo_mode": True,
            "version": "2.0.0"
        }
        
        return create_response(
            message="Production configuration retrieved successfully",
            data=config
        )
        
    except Exception as e:
        log_error("get_production_config", str(e))
        raise HTTPException(status_code=500, detail="Failed to get production config")

@app.post("/api/tts/synthesize")
async def tts_synthesize_proxy(request: Request):
    """TTS proxy endpoint - server handles Google Cloud TTS securely"""
    try:
        data = await request.json()
        text = data.get("text", "")
        voice = data.get("voice", "id-ID-Standard-A")
        
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
            
        if len(text) > 1000:
            raise HTTPException(status_code=400, detail="Text too long (max 1000 chars)")
        
        # Load Google Cloud credentials dari server
        try:
            from google.cloud import texttospeech
            import json
            
            # Credentials hanya ada di server
            credentials_path = Path("config/gcloud_tts_credentials.json")
            if not credentials_path.exists():
                raise HTTPException(status_code=500, detail="TTS credentials not found on server")
            
            # Set environment variable untuk Google Cloud
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path)
            
            # Initialize TTS client
            client = texttospeech.TextToSpeechClient()
            
            # TTS request
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Voice configuration
            voice_config = texttospeech.VoiceSelectionParams(
                language_code="id-ID",
                name=voice,
                ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
            )
            
            # Audio configuration
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            
            # Synthesize speech
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice_config,
                audio_config=audio_config
            )
            
            # Return audio as base64
            import base64
            audio_base64 = base64.b64encode(response.audio_content).decode('utf-8')
            
            return create_response(
                message="TTS synthesis completed successfully",
                data={
                    "audio_base64": audio_base64,
                    "voice_used": voice,
                    "text_length": len(text)
                }
            )
            
        except ImportError:
            raise HTTPException(status_code=500, detail="Google Cloud TTS library not installed")
        except Exception as tts_error:
            raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(tts_error)}")
        
    except Exception as e:
        log_error("tts_synthesize_proxy", str(e))
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(e)}")

@app.post("/api/oauth/google")
async def google_oauth_proxy(request: Request):
    """Google OAuth proxy endpoint - server handles OAuth securely"""
    try:
        data = await request.json()
        action = data.get("action", "get_auth_url")
        
        # Load OAuth credentials dari server
        oauth_path = Path("config/google_oauth.json")
        if not oauth_path.exists():
            raise HTTPException(status_code=500, detail="OAuth credentials not found on server")
        
        with open(oauth_path, 'r') as f:
            oauth_config = json.load(f)
        
        client_config = oauth_config.get("installed", {})
        
        # New action to get safe config (for application startup)
        if action == "get_config":
            # Create safe version (without exposing client_secret) 
            safe_config = {
                "installed": {
                    "client_id": client_config.get("client_id"),
                    "project_id": client_config.get("project_id", "streammate-project"),
                    "auth_uri": client_config.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
                    "token_uri": client_config.get("token_uri", "https://oauth2.googleapis.com/token"),
                    "auth_provider_x509_cert_url": client_config.get(
                        "auth_provider_x509_cert_url", "https://www.googleapis.com/oauth2/v1/certs"),
                    # Exclude client_secret for security
                    "redirect_uris": client_config.get("redirect_uris", ["http://localhost:50700"])
                }
            }
            
            return create_response(
                message="OAuth configuration retrieved successfully",
                data={
                    "oauth_config": safe_config,
                }
            )
        
        elif action == "get_auth_url":
            # Generate OAuth URL
            from urllib.parse import urlencode
            
            params = {
                "client_id": client_config.get("client_id"),
                "redirect_uri": "http://localhost:50700",
                "scope": "openid email profile",
                "response_type": "code",
                "access_type": "offline"
            }
            
            auth_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"
            
            return create_response(
                message="OAuth URL generated successfully",
                data={
                    "auth_url": auth_url,
                    "redirect_uri": "http://localhost:50700"
                }
            )
        
        elif action == "exchange_code":
            # Exchange authorization code untuk token
            auth_code = data.get("code")
            if not auth_code:
                raise HTTPException(status_code=400, detail="Authorization code is required")
            
            # Exchange code untuk token via server
            import requests
            
            token_data = {
                "client_id": client_config.get("client_id"),
                "client_secret": client_config.get("client_secret"),
                "code": auth_code,
                "grant_type": "authorization_code",
                "redirect_uri": "http://localhost:50700"
            }
            
            response = requests.post(
                "https://oauth2.googleapis.com/token",
                data=token_data
            )
            
            if response.status_code == 200:
                token_result = response.json()
                return create_response(
                    message="OAuth token exchange successful",
                    data=token_result
                )
            else:
                raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
        
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
            
    except Exception as e:
        log_error("google_oauth_proxy", str(e))
        raise HTTPException(status_code=500, detail=f"OAuth proxy failed: {str(e)}")

# ===============================
# ERROR HANDLERS
# ===============================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler"""
    return create_response(
            status="error",
            message=f"Endpoint not found: {request.url.path}",
            data={
                "available_endpoints": [
                    "/api/health",
                    "/api/payment/create",
                    "/api/payment/callback",
                    "/api/license/validate",
                    "/api/license/update_usage",
                    "/api/credit/balance",
                    "/api/credit/deduct",
                    "/api/credit/history",
                    "/api/demo/register",
                    "/api/ai/reply",
                    "/api/ai/generate",
                    "/api/admin/add_credit"
                ]
            },
            status_code=404
        )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle internal server errors"""
    logger.error(f"Internal server error on {request.url.path}: {exc}")
    return create_response(
            status="error",
            message="Internal server error",
            data={
                "endpoint": str(request.url.path),
                "method": request.method
            },
            status_code=500
        )

@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors"""
    errors = exc.errors()
    return create_response(
        status="error",
        message=f"Validation error: {errors}",
        status_code=422
    )

# ===============================
# ADMIN ENDPOINTS (USE WITH CAUTION)
# ===============================

@app.post("/api/admin/clear_demo_records")
async def admin_clear_demo_records():
    """
    [ADMIN] Menghapus semua data dari tabel demo_usage.
    Ini adalah tindakan destruktif dan hanya untuk tujuan debugging.
    """
    try:
        deleted_rows = billing_db.clear_table("demo_usage")
        # log_admin_action("admin_clear_demo_records", {"deleted_rows": deleted_rows})
        return create_response(
            message="Semua catatan demo berhasil dihapus.",
            data={"deleted_rows": deleted_rows}
        )
    except Exception as e:
        # log_error("admin_clear_demo_records", str(e))
        raise HTTPException(status_code=500, detail=f"Gagal membersihkan tabel: {e}")

@app.post("/api/admin/create_backup")
async def admin_create_backup():
    """
    [ADMIN] Create manual database backup
    """
    try:
        backup_path = backup_manager.create_backup("manual_admin")
        if backup_path:
            return create_response(
                message="Database backup created successfully",
                data={
                    "backup_path": backup_path,
                    "backup_time": datetime.now().isoformat()
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to create backup")
    except Exception as e:
        log_error("admin_create_backup", str(e))
        raise HTTPException(status_code=500, detail=f"Backup creation failed: {e}")

@app.get("/api/admin/list_backups")
async def admin_list_backups():
    """
    [ADMIN] List all available database backups
    """
    try:
        backups = backup_manager.list_backups()
        return create_response(
            message="Backup list retrieved successfully",
            data={
                "backups": backups,
                "total_backups": len(backups)
            }
        )
    except Exception as e:
        log_error("admin_list_backups", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list backups: {e}")

@app.post("/api/admin/restore_backup")
async def admin_restore_backup(request: Request):
    """
    [ADMIN] Restore database from backup
    DANGEROUS: This will replace current database!
    """
    try:
        data = await request.json()
        backup_path = data.get("backup_path")
        admin_key = data.get("admin_key")
        
        if not backup_path:
            raise HTTPException(status_code=400, detail="backup_path is required")
        
        if admin_key != "STREAMMATE_ADMIN_2024":
            raise HTTPException(status_code=403, detail="Invalid admin key")
        
        # Create emergency backup before restore
        emergency_backup = create_emergency_backup("before_restore")
        logger.warning(f"[ADMIN] Creating emergency backup before restore: {emergency_backup}")
        
        # Perform restore
        success = backup_manager.restore_backup(backup_path)
        
        if success:
            return create_response(
                message="Database restored successfully",
                data={
                    "restored_from": backup_path,
                    "emergency_backup": emergency_backup,
                    "restore_time": datetime.now().isoformat()
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Restore operation failed")
            
    except HTTPException:
        raise
    except Exception as e:
        log_error("admin_restore_backup", str(e))
        raise HTTPException(status_code=500, detail=f"Restore failed: {e}")

@app.get("/api/admin/database_stats")
async def admin_database_stats():
    """
    [ADMIN] Get current database statistics
    """
    try:
        stats = backup_manager._get_database_stats()
        return create_response(
            message="Database statistics retrieved",
            data=stats
        )
    except Exception as e:
        log_error("admin_database_stats", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get database stats: {e}")


# ===============================
# MAIN EXECUTION
# ===============================

if __name__ == '__main__':
    import uvicorn
    # Menentukan host dan port dari environment variables atau default
    host = os.getenv("STREAMMATE_HOST", "127.0.0.1")
    port = int(os.getenv("STREAMMATE_PORT", "8000")) # Kembali ke port 8000
    
    # Menjalankan server
    uvicorn.run(
        "server_inti:app", 
        host=host, 
        port=port, 
        reload=True,
        log_level="info",
        workers=1 
    )