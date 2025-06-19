#!/usr/bin/env python3
"""
Fix Credit Bug - Analisis dan perbaikan bug kredit ganda
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime

def analyze_credit_bug():
    """Analisis bug kredit untuk mursalinasrul@gmail.com"""
    print("=" * 60)
    print("STREAMMATE AI - CREDIT BUG ANALYSIS")
    print("=" * 60)
    
    # 1. Cek database license
    db_path = Path("data/license_data.db")
    if not db_path.exists():
        print("❌ Database tidak ditemukan")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n📊 ANALISIS DATABASE:")
    print("-" * 40)
    
    # Cek semua email yang mirip mursalinasrul
    cursor.execute("""
        SELECT email, credit_balance, credit_used, created_at, updated_at 
        FROM licenses 
        WHERE email LIKE '%mursalin%'
        ORDER BY email
    """)
    
    users = cursor.fetchall()
    
    if not users:
        print("❌ Tidak ada user mursalinasrul ditemukan")
        conn.close()
        return
    
    print(f"📋 Users ditemukan: {len(users)}")
    for user in users:
        email, balance, used, created, updated = user
        print(f"  📧 Email: {email}")
        print(f"     💰 Balance: {balance:,.0f}")
        print(f"     📉 Used: {used:,.0f}")
        print(f"     📅 Created: {created}")
        print(f"     🔄 Updated: {updated}")
        print()
    
    # 2. Cek transaction history
    print("\n💳 TRANSACTION HISTORY:")
    print("-" * 40)
    
    cursor.execute("""
        SELECT email, transaction_type, credit_amount, price, order_id, description, created_at
        FROM transaction_history 
        WHERE email LIKE '%mursalin%'
        ORDER BY created_at DESC
        LIMIT 20
    """)
    
    transactions = cursor.fetchall()
    
    total_purchased = 0
    duplicate_orders = {}
    
    for tx in transactions:
        email, tx_type, amount, price, order_id, desc, created = tx
        print(f"  📝 {created}: {tx_type}")
        print(f"     💰 Amount: {amount:,.0f} (Price: Rp {price:,.0f})")
        print(f"     📋 Order: {order_id}")
        print(f"     📧 Email: {email}")
        print()
        
        if tx_type == 'purchase':
            total_purchased += amount
            
            # Check for duplicate orders
            if order_id in duplicate_orders:
                duplicate_orders[order_id].append((email, amount, created))
            else:
                duplicate_orders[order_id] = [(email, amount, created)]
    
    print(f"💰 Total Purchased: {total_purchased:,.0f} credits")
    
    # 3. Cek duplicate orders
    print(f"\n🔍 DUPLICATE ORDER ANALYSIS:")
    print("-" * 40)
    
    duplicates_found = False
    for order_id, entries in duplicate_orders.items():
        if len(entries) > 1:
            duplicates_found = True
            print(f"🚨 DUPLICATE ORDER: {order_id}")
            for email, amount, created in entries:
                print(f"   📧 {email}: {amount:,.0f} credits at {created}")
            print()
    
    if not duplicates_found:
        print("✅ No duplicate orders found in database")
    
    # 4. Cek email duplication issue
    print(f"\n📧 EMAIL DUPLICATION ANALYSIS:")
    print("-" * 40)
    
    email_variants = []
    for user in users:
        email = user[0]
        if '@gmail.com@gmail.com' in email:
            print(f"🚨 DOUBLE EMAIL BUG: {email}")
            # Extract original email
            original = email.replace('@gmail.com@gmail.com', '@gmail.com')
            email_variants.append((email, original))
    
    if email_variants:
        print(f"\n🔧 RECOMMENDED FIXES:")
        for bad_email, good_email in email_variants:
            print(f"   Merge {bad_email} → {good_email}")
    
    conn.close()
    
    # 5. Cek log files
    print(f"\n📄 LOG FILE ANALYSIS:")
    print("-" * 40)
    
    log_file = Path("logs/server_inti.log")
    if log_file.exists():
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        payment_lines = [line for line in lines if 'mursalin' in line.lower() and 'callback' in line.lower()]
        
        print(f"📋 Payment callback entries: {len(payment_lines)}")
        
        # Show recent payment callbacks
        for line in payment_lines[-10:]:
            if 'Adding' in line and 'credits' in line:
                print(f"   💰 {line.strip()}")
    
    return users, transactions, duplicate_orders, email_variants

def fix_credit_bug():
    """Perbaiki bug kredit"""
    print("\n" + "=" * 60)
    print("CREDIT BUG FIX")
    print("=" * 60)
    
    db_path = Path("data/license_data.db")
    if not db_path.exists():
        print("❌ Database tidak ditemukan")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. Fix email duplication
        print("\n🔧 FIXING EMAIL DUPLICATION...")
        
        # Find double emails
        cursor.execute("""
            SELECT email, credit_balance, credit_used 
            FROM licenses 
            WHERE email LIKE '%@gmail.com@gmail.com'
        """)
        
        double_emails = cursor.fetchall()
        
        for bad_email, balance, used in double_emails:
            good_email = bad_email.replace('@gmail.com@gmail.com', '@gmail.com')
            
            print(f"   🔄 Fixing: {bad_email} → {good_email}")
            
            # Check if good email already exists
            cursor.execute("SELECT email, credit_balance FROM licenses WHERE email = ?", (good_email,))
            existing = cursor.fetchone()
            
            if existing:
                # Merge credits
                existing_balance = existing[1]
                new_balance = existing_balance + balance
                
                print(f"   💰 Merging credits: {existing_balance:,.0f} + {balance:,.0f} = {new_balance:,.0f}")
                
                # Update good email with merged balance
                cursor.execute("""
                    UPDATE licenses 
                    SET credit_balance = ?, updated_at = ?
                    WHERE email = ?
                """, (new_balance, datetime.now().isoformat(), good_email))
                
                # Delete bad email
                cursor.execute("DELETE FROM licenses WHERE email = ?", (bad_email,))
                
            else:
                # Just rename bad email to good email
                cursor.execute("""
                    UPDATE licenses 
                    SET email = ?, updated_at = ?
                    WHERE email = ?
                """, (good_email, datetime.now().isoformat(), bad_email))
            
            # Update transaction history
            cursor.execute("""
                UPDATE transaction_history 
                SET email = ?
                WHERE email = ?
            """, (good_email, bad_email))
        
        # 2. Check for correct credit balance
        print(f"\n💰 VERIFYING CREDIT BALANCE...")
        
        cursor.execute("""
            SELECT email, credit_balance,
                   (SELECT COALESCE(SUM(credit_amount), 0) 
                    FROM transaction_history 
                    WHERE email = licenses.email AND transaction_type = 'purchase') as total_purchased,
                   (SELECT COALESCE(SUM(credit_deducted), 0) 
                    FROM credit_usage_history 
                    WHERE email = licenses.email) as total_used
            FROM licenses 
            WHERE email LIKE '%mursalin%'
        """)
        
        for email, current_balance, purchased, used in cursor.fetchall():
            expected_balance = purchased - used
            
            print(f"   📧 {email}")
            print(f"      💰 Current: {current_balance:,.0f}")
            print(f"      📈 Purchased: {purchased:,.0f}")
            print(f"      📉 Used: {used:,.0f}")
            print(f"      🎯 Expected: {expected_balance:,.0f}")
            
            if abs(current_balance - expected_balance) > 1:
                print(f"      🚨 MISMATCH! Fixing...")
                cursor.execute("""
                    UPDATE licenses 
                    SET credit_balance = ?, updated_at = ?
                    WHERE email = ?
                """, (expected_balance, datetime.now().isoformat(), email))
            else:
                print(f"      ✅ Balance correct")
        
        conn.commit()
        print(f"\n✅ Credit bug fixes applied successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error fixing bug: {e}")
        
    finally:
        conn.close()

def generate_fix_report():
    """Generate laporan perbaikan"""
    print("\n" + "=" * 60)
    print("FINAL VERIFICATION")
    print("=" * 60)
    
    db_path = Path("data/license_data.db")
    if not db_path.exists():
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Final check
    cursor.execute("""
        SELECT email, credit_balance, credit_used,
               (SELECT COUNT(*) FROM transaction_history WHERE email = licenses.email) as tx_count
        FROM licenses 
        WHERE email LIKE '%mursalin%'
    """)
    
    print("📊 FINAL STATE:")
    for email, balance, used, tx_count in cursor.fetchall():
        print(f"   📧 {email}")
        print(f"      💰 Balance: {balance:,.0f}")
        print(f"      📉 Used: {used:,.0f}")
        print(f"      📝 Transactions: {tx_count}")
        print()
    
    conn.close()

if __name__ == "__main__":
    print("StreamMate AI - Credit Bug Analysis & Fix")
    
    # Step 1: Analyze
    result = analyze_credit_bug()
    
    if result:
        users, transactions, duplicates, email_variants = result
        
        if email_variants or duplicates:
            response = input("\nApply fixes? (y/n): ").lower().strip()
            
            if response == 'y':
                # Step 2: Fix
                fix_credit_bug()
                
                # Step 3: Verify
                generate_fix_report()
            else:
                print("Fixes not applied.")
        else:
            print("\n✅ No critical issues found in database")
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60) 