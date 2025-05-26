# modules_client/github_updater.py
import requests
from packaging import version

class GitHubUpdater:
    def __init__(self, repo="yourusername/streammate-releases"):
        self.repo = repo
        self.api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    
    def check_for_updates(self, current_version):
        """Cek update dari GitHub Releases API."""
        try:
            response = requests.get(self.api_url, timeout=10)
            if response.status_code == 200:
                release_data = response.json()
                
                latest_version = release_data["tag_name"].replace("v", "")
                
                if version.parse(latest_version) > version.parse(current_version):
                    return {
                        "available": True,
                        "version": latest_version,
                        "download_url": self._get_download_url(release_data),
                        "changelog": release_data["body"],
                        "file_size": self._get_file_size(release_data),
                        "published_at": release_data["published_at"]
                    }
            
            return {"available": False}
            
        except Exception as e:
            print(f"Update check failed: {e}")
            return {"available": False, "error": str(e)}
    
    def _get_download_url(self, release_data):
        """Ambil URL download untuk Windows executable."""
        for asset in release_data["assets"]:
            if asset["name"].endswith(".exe"):
                return asset["browser_download_url"]
        return None
    
    def _get_file_size(self, release_data):
        """Ambil ukuran file."""
        for asset in release_data["assets"]:
            if asset["name"].endswith(".exe"):
                return asset["size"]
        return 0