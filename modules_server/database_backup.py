# modules_server/database_backup.py
"""
Database Backup and Recovery System
Sistem backup otomatis untuk mencegah kehilangan data kredit
"""

import os
import shutil
import sqlite3
import json
import gzip
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

class DatabaseBackupManager:
    """Manager untuk backup dan recovery database"""
    
    def __init__(self, db_path: str = "data/license_data.db"):
        self.db_path = Path(db_path)
        self.backup_dir = Path("backups/database")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup settings
        self.max_backups = 30  # Keep 30 days of backups
        self.backup_interval_hours = 6  # Backup every 6 hours
        
    def create_backup(self, backup_type: str = "auto") -> str:
        """
        Buat backup database dengan timestamp
        Returns: path to backup file
        """
        try:
            if not self.db_path.exists():
                logger.warning(f"Database file not found: {self.db_path}")
                return None
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"license_data_backup_{timestamp}_{backup_type}.db"
            backup_path = self.backup_dir / backup_filename
            
            # Copy database file
            shutil.copy2(self.db_path, backup_path)
            
            # Create compressed version
            compressed_path = backup_path.with_suffix('.db.gz')
            with open(backup_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove uncompressed version
            backup_path.unlink()
            
            # Create metadata
            metadata = {
                "backup_time": datetime.now().isoformat(),
                "backup_type": backup_type,
                "original_size": self.db_path.stat().st_size,
                "compressed_size": compressed_path.stat().st_size,
                "database_stats": self._get_database_stats()
            }
            
            metadata_path = compressed_path.with_suffix('.db.gz.meta')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"✅ Database backup created: {compressed_path}")
            return str(compressed_path)
            
        except Exception as e:
            logger.error(f"❌ Failed to create backup: {e}")
            return None
    
    def _get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics for backup metadata"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {}
            
            # Count records in each table
            tables = ['licenses', 'transaction_history', 'credit_usage_history']
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[f"{table}_count"] = cursor.fetchone()[0]
                except sqlite3.Error:
                    stats[f"{table}_count"] = 0
            
            # Total credits in system
            try:
                cursor.execute("SELECT SUM(credit_balance) FROM licenses")
                result = cursor.fetchone()[0]
                stats["total_credits"] = float(result) if result else 0.0
            except sqlite3.Error:
                stats["total_credits"] = 0.0
            
            # Active users
            try:
                cursor.execute("SELECT COUNT(*) FROM licenses WHERE is_active = 1")
                stats["active_users"] = cursor.fetchone()[0]
            except sqlite3.Error:
                stats["active_users"] = 0
            
            conn.close()
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups with metadata"""
        backups = []
        
        for backup_file in self.backup_dir.glob("*.db.gz"):
            metadata_file = backup_file.with_suffix('.db.gz.meta')
            
            backup_info = {
                "file": str(backup_file),
                "size": backup_file.stat().st_size,
                "created": datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat()
            }
            
            # Load metadata if available
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        backup_info.update(metadata)
                except Exception as e:
                    logger.warning(f"Failed to load metadata for {backup_file}: {e}")
            
            backups.append(backup_info)
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x['created'], reverse=True)
        return backups
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        Restore database from backup
        Returns: True if successful
        """
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                logger.error(f"Backup file not found: {backup_path}")
                return False
            
            # Create current backup before restore
            current_backup = self.create_backup("pre_restore")
            logger.info(f"Created pre-restore backup: {current_backup}")
            
            # Decompress backup if needed
            if backup_file.suffix == '.gz':
                temp_db = self.db_path.with_suffix('.db.temp')
                with gzip.open(backup_file, 'rb') as f_in:
                    with open(temp_db, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                restore_source = temp_db
            else:
                restore_source = backup_file
            
            # Verify backup integrity
            if not self._verify_database_integrity(restore_source):
                logger.error("Backup file is corrupted or invalid")
                if restore_source != backup_file:
                    restore_source.unlink()  # Remove temp file
                return False
            
            # Stop any database connections (in production, this should be coordinated)
            # For now, we'll just replace the file
            
            # Backup current database
            if self.db_path.exists():
                current_backup_path = self.db_path.with_suffix('.db.current_backup')
                shutil.copy2(self.db_path, current_backup_path)
            
            # Replace with restored database
            shutil.copy2(restore_source, self.db_path)
            
            # Clean up temp file
            if restore_source != backup_file:
                restore_source.unlink()
            
            logger.info(f"✅ Database restored from: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to restore backup: {e}")
            return False
    
    def _verify_database_integrity(self, db_path: Path) -> bool:
        """Verify database file integrity"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if required tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ['licenses', 'transaction_history', 'credit_usage_history']
            for table in required_tables:
                if table not in tables:
                    logger.error(f"Missing required table: {table}")
                    conn.close()
                    return False
            
            # Try to read from each table
            for table in required_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                cursor.fetchone()
            
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")
            return False
    
    def cleanup_old_backups(self):
        """Remove old backups beyond retention limit"""
        try:
            backups = self.list_backups()
            
            if len(backups) > self.max_backups:
                # Remove oldest backups
                backups_to_remove = backups[self.max_backups:]
                
                for backup in backups_to_remove:
                    backup_file = Path(backup['file'])
                    metadata_file = backup_file.with_suffix('.db.gz.meta')
                    
                    # Remove backup file
                    if backup_file.exists():
                        backup_file.unlink()
                        logger.info(f"Removed old backup: {backup_file}")
                    
                    # Remove metadata file
                    if metadata_file.exists():
                        metadata_file.unlink()
                
                logger.info(f"Cleaned up {len(backups_to_remove)} old backups")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
    
    def auto_backup_if_needed(self):
        """Create backup if enough time has passed since last backup"""
        try:
            backups = self.list_backups()
            
            if not backups:
                # No backups exist, create one
                self.create_backup("initial")
                return
            
            # Check if we need a new backup
            last_backup_time = datetime.fromisoformat(backups[0]['created'])
            time_since_backup = datetime.now() - last_backup_time
            
            if time_since_backup.total_seconds() >= self.backup_interval_hours * 3600:
                self.create_backup("auto")
                self.cleanup_old_backups()
            
        except Exception as e:
            logger.error(f"Auto backup check failed: {e}")
    
    def export_user_data(self, email: str) -> Dict[str, Any]:
        """Export all data for a specific user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            user_data = {"email": email, "export_time": datetime.now().isoformat()}
            
            # Get license info
            cursor.execute("SELECT * FROM licenses WHERE email = ?", (email,))
            license_row = cursor.fetchone()
            if license_row:
                cursor.execute("PRAGMA table_info(licenses)")
                columns = [col[1] for col in cursor.fetchall()]
                user_data["license"] = dict(zip(columns, license_row))
            
            # Get transaction history
            cursor.execute("SELECT * FROM transaction_history WHERE email = ?", (email,))
            transactions = cursor.fetchall()
            if transactions:
                cursor.execute("PRAGMA table_info(transaction_history)")
                columns = [col[1] for col in cursor.fetchall()]
                user_data["transactions"] = [dict(zip(columns, tx)) for tx in transactions]
            
            # Get usage history
            cursor.execute("SELECT * FROM credit_usage_history WHERE email = ?", (email,))
            usage = cursor.fetchall()
            if usage:
                cursor.execute("PRAGMA table_info(credit_usage_history)")
                columns = [col[1] for col in cursor.fetchall()]
                user_data["usage_history"] = [dict(zip(columns, use)) for use in usage]
            
            conn.close()
            return user_data
            
        except Exception as e:
            logger.error(f"Failed to export user data for {email}: {e}")
            return {}

# Global instance
backup_manager = DatabaseBackupManager()

def create_emergency_backup(reason: str = "emergency") -> str:
    """Create emergency backup with reason"""
    return backup_manager.create_backup(f"emergency_{reason}")

def restore_from_backup(backup_path: str) -> bool:
    """Restore database from backup file"""
    return backup_manager.restore_backup(backup_path)

def auto_backup():
    """Perform automatic backup if needed"""
    backup_manager.auto_backup_if_needed() 