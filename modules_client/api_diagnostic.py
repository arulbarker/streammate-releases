#!/usr/bin/env python3
"""
StreamMate AI - API Connection Diagnostic Tool
==============================================

Tool diagnostik untuk:
1. Test koneksi VPS server vs local server
2. Test AI generation functionality dengan berbagai fallback method
3. Verify endpoint availability dan response format
4. Troubleshooting guide otomatis

PENTING: File ini jangan dihapus karena diperlukan untuk troubleshooting
         ketika auto-reply tidak bekerja atau ada masalah koneksi.
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def test_api_bridge():
    """Test API bridge connectivity dan server selection"""
    print("🧪 Testing API Bridge Connectivity...")
    print("=" * 50)
    
    try:
        from modules_client.api import api_bridge, test_api_connection
        
        print(f"📍 VPS Server: {api_bridge.vps_server}")
        print(f"📍 Local Server: {api_bridge.local_server}")
        print(f"📍 Active Server: {api_bridge.active_server}")
        
        # Test connections
        print(f"\n🔍 Testing connections...")
        status = test_api_connection()
        
        print(f"✅ VPS (69.62.79.238): {'🟢 ONLINE' if status['vps_server'] else '🔴 OFFLINE'}")
        print(f"✅ Local (localhost:8000): {'🟢 ONLINE' if status['local_server'] else '🔴 OFFLINE'}")
        print(f"✅ Direct DeepSeek: {'🟢 AVAILABLE' if status['deepseek_direct'] else '🔴 NO API KEY'}")
        
        return status
        
    except Exception as e:
        print(f"❌ API Bridge test failed: {e}")
        return None

def test_ai_generation():
    """Test AI generation functionality dengan berbagai test case"""
    print(f"\n🤖 Testing AI Generation...")
    print("=" * 30)
    
    try:
        from modules_client.api import generate_reply
        
        test_prompts = [
            {
                "name": "Greeting Test",
                "prompt": "Penonton TestUser bertanya: halo bang apa kabar?",
                "expected_keywords": ["hai", "halo", "kabar", "testuser"]
            },
            {
                "name": "Gaming Question",
                "prompt": "Penonton Viewer123 bertanya: lagi main game apa?",
                "expected_keywords": ["game", "main", "viewer"]
            },
            {
                "name": "Simple Test",
                "prompt": "Test prompt sederhana",
                "expected_keywords": ["test", "prompt"]
            }
        ]
        
        success_count = 0
        ai_method_used = "unknown"
        
        for i, test_case in enumerate(test_prompts, 1):
            print(f"\n🧪 Test {i} - {test_case['name']}: {test_case['prompt'][:50]}...")
            
            try:
                result = generate_reply(test_case['prompt'])
                print(f"✅ Result: {result[:100]}...")
                print(f"📏 Length: {len(result)} chars")
                
                # Analyze response quality
                if any(word in result.lower() for word in ["fallback", "maintenance", "bermasalah"]):
                    print(f"⚠️  WARNING: Using fallback response")
                    ai_method_used = "fallback"
                elif len(result) > 50 and any(keyword in result.lower() for keyword in test_case['expected_keywords'][:2]):
                    print(f"🎉 SUCCESS: Valid AI response with context")
                    if ai_method_used == "unknown":
                        ai_method_used = "ai_service"
                    success_count += 1
                elif len(result) > 10:
                    print(f"✅ OK: Valid response")
                    success_count += 1
                else:
                    print(f"⚠️  WARNING: Response too short")
                    
            except Exception as e:
                print(f"❌ FAIL: {e}")
        
        print(f"\n📊 AI Generation Summary:")
        print(f"   Success Rate: {success_count}/{len(test_prompts)} ({success_count/len(test_prompts)*100:.1f}%)")
        print(f"   Method Used: {ai_method_used}")
        
        return success_count > 0, ai_method_used
        
    except Exception as e:
        print(f"❌ AI generation test failed: {e}")
        return False, "error"

def check_vps_endpoints():
    """Check VPS endpoints availability dan response format"""
    print(f"\n🌐 Testing VPS Endpoints...")
    print("=" * 30)
    
    endpoints_status = {}
    
    try:
        import requests
        
        base_url = "http://69.62.79.238:8000"
        
        # Test endpoints
        endpoints_to_test = [
            {
                "name": "Health Check",
                "method": "GET",
                "url": f"{base_url}/api/health",
                "timeout": 5
            },
            {
                "name": "AI Reply (Existing)", 
                "method": "POST",
                "url": f"{base_url}/api/ai/reply",
                "timeout": 10,
                "data": {"text": "Test prompt"}
            },
            {
                "name": "AI Generate (New)",
                "method": "POST", 
                "url": f"{base_url}/api/ai/generate",
                "timeout": 10,
                "data": {"prompt": "Test prompt"}
            }
        ]
        
        for endpoint in endpoints_to_test:
            print(f"🔍 Testing {endpoint['name']}...")
            
            try:
                if endpoint['method'] == 'GET':
                    response = requests.get(endpoint['url'], timeout=endpoint['timeout'])
                else:
                    response = requests.post(
                        endpoint['url'],
                        json=endpoint.get('data', {}),
                        headers={"Content-Type": "application/json"},
                        timeout=endpoint['timeout']
                    )
                
                print(f"   Status: {response.status_code}")
                endpoints_status[endpoint['name']] = response.status_code
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if endpoint['name'] == "Health Check":
                            print(f"   Server Version: {data.get('server_version', 'unknown')}")
                            ai_module = data.get('data', {}).get('components', {}).get('ai_module', 'unknown')
                            print(f"   AI Module: {ai_module}")
                        elif "AI" in endpoint['name']:
                            reply = ""
                            if "data" in data and isinstance(data["data"], dict):
                                reply = data["data"].get("reply", "")
                            elif "reply" in data:
                                reply = data.get("reply", "")
                            
                            if reply:
                                print(f"   AI Reply: {reply[:50]}...")
                                print(f"   Reply Length: {len(reply)} chars")
                            else:
                                print(f"   ⚠️  No reply in response")
                                
                    except json.JSONDecodeError:
                        print(f"   ⚠️  Non-JSON response")
                        
                elif response.status_code == 404:
                    print(f"   ❌ ENDPOINT NOT FOUND")
                    if endpoint['name'] == "AI Generate (New)":
                        print(f"   💡 Hint: Endpoint belum ditambahkan ke VPS server")
                else:
                    print(f"   ⚠️  Error: {response.text[:100]}")
                    
            except requests.exceptions.Timeout:
                print(f"   ❌ TIMEOUT")
                endpoints_status[endpoint['name']] = "timeout"
            except requests.exceptions.ConnectionError:
                print(f"   ❌ CONNECTION ERROR")
                endpoints_status[endpoint['name']] = "connection_error"
            except Exception as e:
                print(f"   ❌ ERROR: {e}")
                endpoints_status[endpoint['name']] = "error"
        
        return endpoints_status
        
    except Exception as e:
        print(f"❌ VPS endpoint test failed: {e}")
        return {}

def generate_troubleshooting_report(bridge_status, ai_status, ai_method, endpoints_status):
    """Generate troubleshooting report dan recommendations"""
    print(f"\n📋 DIAGNOSTIC REPORT")
    print("=" * 50)
    
    # Overall Status
    print(f"🎯 Overall Status:")
    if ai_status and ai_method in ["ai_service"]:
        print(f"   ✅ AUTO-REPLY FULLY FUNCTIONAL")
    elif ai_status and ai_method == "fallback":
        print(f"   ⚠️  AUTO-REPLY USING FALLBACK (Still working)")
    else:
        print(f"   ❌ AUTO-REPLY NOT WORKING")
    
    # Connection Status
    print(f"\n🌐 Connection Status:")
    if bridge_status:
        print(f"   VPS Server: {'✅ OK' if bridge_status.get('vps_server') else '❌ FAILED'}")
        print(f"   Local Server: {'✅ OK' if bridge_status.get('local_server') else '❌ FAILED'}")
        print(f"   DeepSeek Direct: {'✅ OK' if bridge_status.get('deepseek_direct') else '❌ NO KEY'}")
        print(f"   Active Server: {bridge_status.get('active_server', 'unknown')}")
    
    # Endpoint Status
    print(f"\n🔌 Endpoint Status:")
    for endpoint, status in endpoints_status.items():
        if status == 200:
            print(f"   {endpoint}: ✅ WORKING")
        elif status == 404:
            print(f"   {endpoint}: ❌ NOT FOUND")
        elif status == "timeout":
            print(f"   {endpoint}: ⏰ TIMEOUT")
        elif status == "connection_error":
            print(f"   {endpoint}: 🔌 CONNECTION ERROR")
        else:
            print(f"   {endpoint}: ❌ ERROR ({status})")
    
    # Recommendations
    print(f"\n💡 TROUBLESHOOTING RECOMMENDATIONS:")
    
    if not ai_status:
        print(f"🔧 AUTO-REPLY NOT WORKING:")
        print(f"   1. Check VPS server is running: ssh 69.62.79.238")
        print(f"   2. Verify server process: ps aux | grep server_inti")
        print(f"   3. Check server logs for errors")
        print(f"   4. Restart server if needed")
    
    elif ai_method == "fallback":
        print(f"🔧 USING FALLBACK RESPONSES:")
        print(f"   1. VPS AI endpoint is not responding properly")
        print(f"   2. Check DEEPSEEK_API_KEY in VPS .env file")
        print(f"   3. Verify DeepSeek API quota/credits")
        print(f"   4. Check VPS server logs for AI errors")
    
    if endpoints_status.get("AI Generate (New)") == 404:
        print(f"🔧 MISSING NEW ENDPOINT:")
        print(f"   1. /api/ai/generate endpoint belum ditambahkan")
        print(f"   2. Follow manual fix instructions in vps_manual_fix.txt")
        print(f"   3. Current workaround: Using /api/ai/reply (working)")
    
    if not bridge_status or not bridge_status.get('vps_server'):
        print(f"🔧 VPS CONNECTION ISSUES:")
        print(f"   1. Check VPS server is accessible: ping 69.62.79.238")
        print(f"   2. Check port 80 is open: telnet 69.62.79.238 80")
        print(f"   3. Verify firewall rules on VPS")
        print(f"   4. Check server process is running on VPS")
    
    # Success Case
    if ai_status and ai_method == "ai_service":
        print(f"✅ SYSTEM WORKING PERFECTLY:")
        print(f"   - Auto-reply will work with real AI responses")
        print(f"   - TTS will work if audio system supports it")
        print(f"   - No action needed")

def save_diagnostic_log():
    """Save diagnostic results to log file"""
    log_file = Path("logs/api_diagnostic.log")
    log_file.parent.mkdir(exist_ok=True)
    
    # Create simple log entry
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n=== API Diagnostic - {timestamp} ===\n")
        f.write("Check console output for detailed results\n")
    
    print(f"\n📄 Diagnostic log saved to: {log_file}")

def main():
    """Main diagnostic function"""
    print("🔍 StreamMate AI - API Connection Diagnostic")
    print("=" * 60)
    print("Tool ini membantu diagnose masalah auto-reply dan koneksi API")
    print("=" * 60)
    
    # Run all tests
    bridge_status = test_api_bridge()
    ai_status, ai_method = test_ai_generation()
    endpoints_status = check_vps_endpoints()
    
    # Generate report
    generate_troubleshooting_report(bridge_status, ai_status, ai_method, endpoints_status)
    
    # Save log
    save_diagnostic_log()
    
    print(f"\n" + "=" * 60)
    print(f"🚀 Diagnostic completed. Use this info to fix any issues.")
    print(f"=" * 60)

if __name__ == "__main__":
    main() 