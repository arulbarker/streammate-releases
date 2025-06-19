#!/usr/bin/env python3
"""
StreamMate AI - Upload to GitHub
Script untuk mengupload file ke GitHub releases
"""

import os
import sys
import json
import requests
import argparse
from pathlib import Path
from datetime import datetime

def create_github_release(token, owner, repo, tag_name, name, body, draft=False, prerelease=False):
    """Create GitHub release"""
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "tag_name": tag_name,
        "name": name,
        "body": body,
        "draft": draft,
        "prerelease": prerelease
    }
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        print(f"✅ Release created: {name}")
        return response.json()
    else:
        print(f"❌ Failed to create release: {response.status_code}")
        print(response.text)
        return None

def upload_asset(token, upload_url, file_path, content_type="application/zip"):
    """Upload asset to GitHub release"""
    # Extract upload URL template
    upload_url = upload_url.split("{")[0]
    
    # Add filename parameter
    filename = os.path.basename(file_path)
    url = f"{upload_url}?name={filename}"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": content_type
    }
    
    with open(file_path, "rb") as f:
        response = requests.post(url, headers=headers, data=f)
    
    if response.status_code == 201:
        print(f"✅ Asset uploaded: {filename}")
        return response.json()
    else:
        print(f"❌ Failed to upload asset: {response.status_code}")
        print(response.text)
        return None

def get_changelog_from_file():
    """Get latest changelog from CHANGELOG.md"""
    changelog_file = Path("CHANGELOG.md")
    if not changelog_file.exists():
        return "New release"
    
    with open(changelog_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find the first version section
    version_pos = content.find("## [v")
    if version_pos == -1:
        return "New release"
    
    # Find the next version section
    next_version_pos = content.find("## [v", version_pos + 1)
    if next_version_pos == -1:
        # Only one version section
        changelog = content[version_pos:].strip()
    else:
        changelog = content[version_pos:next_version_pos].strip()
    
    return changelog

def main():
    parser = argparse.ArgumentParser(description="Upload StreamMate AI release to GitHub")
    parser.add_argument("--token", help="GitHub API token", required=True)
    parser.add_argument("--owner", help="GitHub repository owner", default="arulbarker")
    parser.add_argument("--repo", help="GitHub repository name", default="streammate-releases")
    parser.add_argument("--version", help="Version number (e.g., 1.0.2)", required=True)
    parser.add_argument("--file", help="Path to release file (ZIP or EXE)", required=True)
    parser.add_argument("--draft", help="Create as draft release", action="store_true")
    parser.add_argument("--prerelease", help="Mark as pre-release", action="store_true")
    
    args = parser.parse_args()
    
    # Verify file exists
    if not os.path.exists(args.file):
        print(f"❌ Error: File {args.file} not found")
        return 1
    
    # Get changelog
    changelog = get_changelog_from_file()
    
    # Create tag name
    tag_name = f"v{args.version}"
    release_name = f"StreamMate AI {tag_name} - Production Release"
    
    # Create release
    release = create_github_release(
        args.token, args.owner, args.repo, tag_name, release_name, changelog,
        draft=args.draft, prerelease=args.prerelease
    )
    
    if not release:
        return 1
    
    # Upload asset
    content_type = "application/zip" if args.file.endswith(".zip") else "application/octet-stream"
    asset = upload_asset(args.token, release["upload_url"], args.file, content_type)
    
    if not asset:
        return 1
    
    print("\n✨ Release uploaded successfully!")
    print(f"🔗 Release URL: {release['html_url']}")
    print(f"📦 Download URL: {asset['browser_download_url']}")
    
    # Update update-info.json with download URL
    try:
        info_file = Path("update-info.json")
        if info_file.exists():
            with open(info_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if "download_info" not in data:
                data["download_info"] = {}
            
            data["download_info"]["url"] = asset['browser_download_url']
            
            with open(info_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            print("✅ Updated update-info.json with download URL")
    except Exception as e:
        print(f"⚠️ Warning: Failed to update update-info.json: {e}")
    
    return 0

if __name__ == "__main__":
    exit(main()) 