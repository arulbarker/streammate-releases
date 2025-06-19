# StreamMate AI - Development Guide
## Panduan Development Setelah Release

### 🎯 **SKENARIO DEVELOPMENT SETELAH RELEASE**

Setelah aplikasi di-release, Anda tetap bisa melakukan development dengan beberapa strategi:

---

## 🔧 **1. DUAL ENVIRONMENT SETUP**

### **A. Production Environment (VPS)**
```
🌐 URL: http://69.62.79.238:8000
📊 Purpose: Real users, stable version
🗄️ Database: license_data.db (production data)
💳 Payment: iPaymu Production mode
🔒 Security: Production admin keys
```

### **B. Development Environment (Local)**
```
🌐 URL: http://localhost:8001
📊 Purpose: Testing new features
🗄️ Database: license_data_dev.db (test data)
💳 Payment: iPaymu Sandbox mode
🔒 Security: Development admin keys
```

---

## 🚀 **2. CARA MENJALANKAN DEVELOPMENT**

### **Option 1: Development Server (RECOMMENDED)**
```bash
# Jalankan development server
python server_dev.py

# Server akan berjalan di:
# http://localhost:8001
```

### **Option 2: Server Inti dengan Environment**
```bash
# Set environment ke development
set STREAMMATE_ENV=development
set STREAMMATE_DEBUG=true

# Jalankan server dengan port berbeda
python -m uvicorn server_inti:app --host localhost --port 8001 --reload
```

### **Option 3: Separate Development VPS**
```bash
# Setup VPS terpisah untuk development
# Misal: http://dev.streammateai.com:8000
```

---

## 📁 **3. STRUKTUR DEVELOPMENT**

```
streammate_ai_v1.00/
├── server_inti.py          # Main server (production ready)
├── server_dev.py           # Development server
├── config/
│   ├── production_config.json    # Production settings
│   └── development_config.json   # Development settings
├── data/
│   ├── license_data.db           # Production database
│   └── license_data_dev.db       # Development database
└── modules_server/
    ├── license_manager.py        # Shared modules
    └── ...
```

---

## 🔄 **4. WORKFLOW DEVELOPMENT**

### **Step 1: Development Phase**
```bash
# 1. Jalankan development server
python server_dev.py

# 2. Test fitur baru di http://localhost:8001
# 3. Debug dengan database terpisah
# 4. Test payment dengan sandbox mode
```

### **Step 2: Testing Phase**
```bash
# 1. Test semua endpoint
python test_all_endpoints.py

# 2. Test payment system
python test_payment_system.py

# 3. Test backup system
python test_backup_system.py
```

### **Step 3: Deployment Phase**
```bash
# 1. Upload ke production server
scp server_inti.py root@69.62.79.238:/root/streammateai_server/

# 2. Restart production server
ssh root@69.62.79.238 "systemctl restart streammateai.service"

# 3. Verify production
curl http://69.62.79.238:8000/api/health
```

---

## ⚙️ **5. CONFIGURATION MANAGEMENT**

### **Development Config (development_config.json)**
```json
{
    "environment": "development",
    "server": {
        "host": "localhost",
        "port": 8001,
        "debug": true
    },
    "database": {
        "path": "data/license_data_dev.db"
    },
    "payment": {
        "mode": "sandbox"
    }
}
```

### **Production Config (production_config.json)**
```json
{
    "environment": "production",
    "server": {
        "host": "0.0.0.0",
        "port": 8000,
        "debug": false
    },
    "database": {
        "path": "data/license_data.db"
    },
    "payment": {
        "mode": "production"
    }
}
```

---

## 🛡️ **6. KEAMANAN DEVELOPMENT**

### **Environment Variables**
```bash
# Development
STREAMMATE_ENV=development
STREAMMATE_ADMIN_KEY=dev_admin_2025
IPAYMU_MODE=sandbox

# Production
STREAMMATE_ENV=production
STREAMMATE_ADMIN_KEY=tolo_admin_2025
IPAYMU_MODE=production
```

### **Database Isolation**
- ✅ Production: `license_data.db`
- ✅ Development: `license_data_dev.db`
- ✅ No cross-contamination

---

## 🔄 **7. CONTINUOUS DEVELOPMENT PROCESS**

### **Daily Development Workflow:**
1. 🔧 **Morning:** Start development server
2. 💻 **Code:** Develop new features locally
3. 🧪 **Test:** Test with development database
4. 📝 **Document:** Update code and tests
5. 🚀 **Deploy:** Push to production when ready

### **Feature Development Cycle:**
1. **Branch/Version Control**
2. **Local Development** (port 8001)
3. **Testing** (automated tests)
4. **Staging** (optional separate server)
5. **Production Deployment** (port 8000)

---

## 📊 **8. MONITORING & DEBUGGING**

### **Development Monitoring:**
```bash
# Monitor development server
tail -f logs/development.log

# Debug API calls
curl http://localhost:8001/api/health

# Test new features
python test_new_features.py
```

### **Production Monitoring:**
```bash
# Monitor production server
ssh root@69.62.79.238 "tail -f /root/streammateai_server/server.log"

# Check service status
ssh root@69.62.79.238 "systemctl status streammateai.service"
```

---

## 🎯 **9. BEST PRACTICES**

### **DO's:**
- ✅ Always develop on separate port/database
- ✅ Use environment variables for config
- ✅ Test thoroughly before production deploy
- ✅ Keep production and development isolated
- ✅ Backup before major updates

### **DON'Ts:**
- ❌ Never develop directly on production
- ❌ Don't mix production and development data
- ❌ Don't test payments on production
- ❌ Don't deploy untested code
- ❌ Don't modify production database directly

---

## 🚀 **KESIMPULAN**

**Ya, Anda bisa tetap develop setelah release!**

**Cara terbaik:**
1. **Production Server** tetap jalan di VPS (port 8000)
2. **Development Server** jalan di lokal (port 8001)
3. **Database terpisah** untuk development
4. **Testing lengkap** sebelum deploy ke production
5. **Deployment otomatis** dengan script

**Keuntungan:**
- 🔒 Production tetap aman dan stabil
- 🔧 Development fleksibel dan cepat
- 🧪 Testing isolated dan comprehensive
- 🚀 Deployment controlled dan tracked 