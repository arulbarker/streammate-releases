#!/usr/bin/env python3
"""
StreamMate AI - Prepare Release Script
Script untuk mempersiapkan rilis dengan perhitungan checksum dan pembaruan update-info.json
"""

import os
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime

def calculate_checksum(file_path):
    """Calculate SHA-256 checksum dari file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_file_size(file_path):
    """Get file size in bytes"""
    return os.path.getsize(file_path)

def update_info_json(version, file_path, changelog_items=None):
    """Update update-info.json dengan informasi rilis baru"""
    # Path ke update-info.json
    info_file = Path("update-info.json")
    
    # Load existing data jika ada
    if info_file.exists():
        with open(info_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}
    
    # Update version info
    data["latest_version"] = version
    data["release_date"] = datetime.now().strftime("%Y-%m-%d")
    
    # Set minimum version jika belum ada
    if "minimum_version" not in data:
        data["minimum_version"] = "1.0.0"
    
    # Update changelog
    if changelog_items:
        data["changelog"] = changelog_items
    elif "changelog" not in data:
        data["changelog"] = [f"Update to version {version}"]
    
    # Update download info
    if "download_info" not in data:
        data["download_info"] = {}
    
    # Calculate checksum and size
    file_size = get_file_size(file_path)
    checksum = calculate_checksum(file_path)
    
    # Update download info
    data["download_info"]["file_size"] = file_size
    data["download_info"]["checksum"] = f"sha256:{checksum}"
    
    # Set download URL
    filename = os.path.basename(file_path)
    data["download_info"]["url"] = f"https://github.com/arulbarker/streammate-releases/releases/download/v{version}/{filename}"
    
    # Write updated data
    with open(info_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Updated update-info.json with version {version}")
    print(f"📦 File size: {file_size} bytes")
    print(f"🔒 SHA-256: {checksum}")

def update_version_file(version):
    """Update version.txt file"""
    with open("version.txt", "w", encoding="utf-8") as f:
        f.write(f"V.{version}")
    print(f"✅ Updated version.txt to V.{version}")

def update_changelog_md(version, changelog_items=None):
    """Update CHANGELOG.md dengan versi baru"""
    changelog_file = Path("CHANGELOG.md")
    
    # Default changelog jika tidak ada
    if not changelog_items:
        changelog_items = [f"Update to version {version}"]
    
    # Read existing content
    if changelog_file.exists():
        with open(changelog_file, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = "# StreamMate AI Changelog\n\nAll notable changes to this project will be documented in this file.\n\n"
    
    # Create new entry
    today = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"## [v{version}] - {today}\n\n"
    
    # Add features section if there are items
    new_entry += "### ✨ New Features\n"
    for item in changelog_items:
        new_entry += f"- {item}\n"
    
    new_entry += "\n"
    
    # Insert after header
    header_end = content.find("\n\n") + 2
    updated_content = content[:header_end] + new_entry + content[header_end:]
    
    # Write updated content
    with open(changelog_file, "w", encoding="utf-8") as f:
        f.write(updated_content)
    
    print(f"✅ Updated CHANGELOG.md with version {version}")

def main():
    parser = argparse.ArgumentParser(description="Prepare StreamMate AI release")
    parser.add_argument("version", help="Version number (e.g., 1.0.2)")
    parser.add_argument("file", help="Path to release file (ZIP or EXE)")
    parser.add_argument("--changelog", nargs="+", help="Changelog items")
    
    args = parser.parse_args()
    
    # Verify file exists
    if not os.path.exists(args.file):
        print(f"❌ Error: File {args.file} not found")
        return 1
    
    # Update files
    update_version_file(args.version)
    update_changelog_md(args.version, args.changelog)
    update_info_json(args.version, args.file, args.changelog)
    
    print("\n✨ Release preparation complete!")
    print(f"📝 Next steps:")
    print(f"1. Commit changes to Git")
    print(f"2. Create tag v{args.version}")
    print(f"3. Push to GitHub")
    print(f"4. Create GitHub release with tag v{args.version}")
    print(f"5. Upload {os.path.basename(args.file)} to the release")
    
    return 0

if __name__ == "__main__":
    exit(main()) 