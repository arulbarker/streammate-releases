# modules_client/avatar_manager.py
import os
import json
import threading
import time
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

class AvatarManager(QObject):
    """
    Manages 3D avatars for VTuber-like functionality.
    Basic implementation that can be extended with more advanced 3D capabilities.
    """
    
    # Signals
    statusChanged = pyqtSignal(str)
    avatarListUpdated = pyqtSignal(list)
    avatarLoaded = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        # Setup paths
        self.avatar_dir = Path("avatars")
        self.avatar_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.avatar_dir / "avatar_config.json"
        self.current_avatar = None
        self.avatar_window = None
        self.avatar_thread = None
        
        # Load avatars
        self.avatars = self._load_avatars()
        
        # Signal initial status
        self.statusChanged.emit("Avatar manager initialized")
    
    def _load_avatars(self):
        """Load avatar configuration."""
        if not self.config_file.exists():
            # Create default config
            config = {"avatars": []}
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            return []
        
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("avatars", [])
        except Exception as e:
            self.statusChanged.emit(f"Error loading avatars: {str(e)}")
            return []
    
    def _save_avatars(self):
        """Save avatar configuration."""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump({"avatars": self.avatars}, f, indent=2)
            self.statusChanged.emit("Avatar configuration saved")
        except Exception as e:
            self.statusChanged.emit(f"Error saving avatars: {str(e)}")
    
    def get_avatar_list(self):
        """Get list of available avatars."""
        return self.avatars
    
    def create_new_avatar(self):
        """
        Create a new avatar using a simple placeholder implementation.
        In a real implementation, this would open a character creation UI.
        """
        # For demonstration, create a placeholder avatar
        new_avatar = {
            "name": f"Avatar {len(self.avatars) + 1}",
            "path": str(self.avatar_dir / f"avatar_{len(self.avatars) + 1}.glb"),
            "created_at": time.time()
        }
        
        # Add to avatar list
        self.avatars.append(new_avatar)
        
        # Save configuration
        self._save_avatars()
        
        # Emit updated list
        self.avatarListUpdated.emit(self.avatars)
        self.statusChanged.emit(f"Created new avatar: {new_avatar['name']}")
    
    def import_avatar(self, file_path, name):
        """
        Import avatar from file.
        
        Args:
            file_path: Path to GLB file
            name: Name for the avatar
        """
        try:
            # Copy file to avatar directory
            import shutil
            src_path = Path(file_path)
            dst_path = self.avatar_dir / src_path.name
            
            # Check if file already exists
            if dst_path.exists():
                # Add timestamp to make unique
                stem = dst_path.stem
                suffix = dst_path.suffix
                dst_path = self.avatar_dir / f"{stem}_{int(time.time())}{suffix}"
            
            # Copy file
            shutil.copy2(src_path, dst_path)
            
            # Create avatar entry
            new_avatar = {
                "name": name,
                "path": str(dst_path),
                "imported": True,
                "created_at": time.time()
            }
            
            # Add to avatar list
            self.avatars.append(new_avatar)
            
            # Save configuration
            self._save_avatars()
            
            # Emit updated list
            self.avatarListUpdated.emit(self.avatars)
            self.statusChanged.emit(f"Imported avatar: {name}")
            
        except Exception as e:
            self.statusChanged.emit(f"Error importing avatar: {str(e)}")
    
    def remove_avatar(self, index):
        """
        Remove avatar from list.
        
        Args:
            index: Index of avatar to remove
        """
        if 0 <= index < len(self.avatars):
            avatar = self.avatars[index]
            
            # Remove file if it exists
            path = Path(avatar.get("path", ""))
            if path.exists():
                try:
                    path.unlink()
                except Exception as e:
                    self.statusChanged.emit(f"Error deleting avatar file: {str(e)}")
            
            # Remove from list
            self.avatars.pop(index)
            
            # Save configuration
            self._save_avatars()
            
            # Emit updated list
            self.avatarListUpdated.emit(self.avatars)
            self.statusChanged.emit(f"Removed avatar: {avatar.get('name')}")
    
    def load_avatar(self, index):
        """
        Load avatar for use.
        
        Args:
            index: Index of avatar to load
        """
        if 0 <= index < len(self.avatars):
            self.current_avatar = self.avatars[index]
            self.avatarLoaded.emit(self.current_avatar.get("path", ""))
            self.statusChanged.emit(f"Loaded avatar: {self.current_avatar.get('name')}")
    
    def show_avatar_window(self, green_screen=False):
        """
        Show avatar in a separate window.
        
        Args:
            green_screen: Whether to use green screen background
        """
        if not self.current_avatar:
            self.statusChanged.emit("No avatar loaded")
            return
        
        # Close existing window
        self.close_avatar_window()
        
        # Start new window thread
        self.avatar_thread = threading.Thread(
            target=self._run_avatar_window,
            args=(self.current_avatar.get("path"), green_screen),
            daemon=True
        )
        self.avatar_thread.start()
        
        self.statusChanged.emit("Avatar window opened")
    
    def close_avatar_window(self):
        """Close avatar window if open."""
        # This is a placeholder implementation
        # In a real implementation, you would send a signal to close the window
        if hasattr(self, 'avatar_window') and self.avatar_window:
            try:
                self.avatar_window = None
                self.statusChanged.emit("Avatar window closed")
            except:
                pass
    
    def _run_avatar_window(self, avatar_path, green_screen=False):
        """
        Run avatar window in a separate thread.
        
        Args:
            avatar_path: Path to avatar file
            green_screen: Whether to use green screen background
        """
        try:
            # Try using tkinter for a simple window
            import tkinter as tk
            from tkinter import ttk
            
            root = tk.Tk()
            root.title("StreamMate Avatar")
            root.geometry("400x400")
            root.configure(bg="#00FF00" if green_screen else "#333333")
            
            # Add label explaining this is a placeholder
            label = ttk.Label(
                root, 
                text=f"This is a placeholder for a 3D avatar viewer.\n\nAvatar: {Path(avatar_path).name}",
                background="#00FF00" if green_screen else "#333333",
                foreground="black" if green_screen else "white",
                font=("Arial", 12)
            )
            label.pack(expand=True)
            
            # Store reference
            self.avatar_window = root
            
            # Run window
            root.mainloop()
            
        except Exception as e:
            self.statusChanged.emit(f"Error showing avatar window: {str(e)}")