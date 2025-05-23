#!/usr/bin/env python3
"""
Version Bump Script untuk StreamMate AI
Script untuk menaikkan versi dan create Git tag untuk release
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

VERSION_FILE = "version.txt"

def get_current_version():
    """Ambil versi saat ini"""
    try:
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"

def parse_version(version_str):
    """Parse version string menjadi tuple (major, minor, patch)"""
    try:
        parts = version_str.split('.')
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return (0, 0, 0)

def version_to_string(version_tuple):
    """Convert version tuple ke string"""
    return f"{version_tuple[0]}.{version_tuple[1]}.{version_tuple[2]}"

def bump_version(current_version, bump_type):
    """Bump version berdasarkan tipe"""
    major, minor, patch = parse_version(current_version)
    
    if bump_type == "major":
        return version_to_string((major + 1, 0, 0))
    elif bump_type == "minor":
        return version_to_string((major, minor + 1, 0))
    elif bump_type == "patch":
        return version_to_string((major, minor, patch + 1))
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")

def update_version_file(new_version):
    """Update file version.txt"""
    with open(VERSION_FILE, 'w') as f:
        f.write(new_version)
    print(f"✅ Updated {VERSION_FILE}: {new_version}")

def update_config_files(new_version):
    """Update versi di file konfigurasi lain"""
    files_to_update = [
        ("config/settings.json", "app_version"),
        ("ui/main_window.py", "version = "),
    ]
    
    for file_path, pattern in files_to_update:
        if os.path.exists(file_path):
            try:
                if file_path.endswith('.json'):
                    import json
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    data[pattern] = f"v{new_version}"
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"✅ Updated {file_path}")
                else:
                    # For Python files, simple string replacement
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Look for version patterns
                    if 'version = "' in content:
                        content = content.replace(
                            content[content.find('version = "'):content.find('"', content.find('version = "') + 10) + 1],
                            f'version = "v{new_version}"'
                        )
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        print(f"✅ Updated {file_path}")
            except Exception as e:
                print(f"⚠️  Warning: Could not update {file_path}: {e}")

def create_changelog_entry(version, bump_type):
    """Buat entry changelog"""
    changelog_file = "CHANGELOG.md"
    
    # Template changelog entry
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    if bump_type == "major":
        template = f"""## [v{version}] - {date_str}

### 🚀 Major Changes
- New major feature implementation
- Breaking changes (if any)
- Architecture improvements

### 🐛 Bug Fixes
- Critical bug fixes
- Performance improvements

### 📝 Notes
- Update instructions for users
- Migration guide (if needed)

"""
    elif bump_type == "minor":
        template = f"""## [v{version}] - {date_str}

### ✨ New Features
- New feature additions
- Feature enhancements
- UI/UX improvements

### 🐛 Bug Fixes
- Bug fixes and optimizations
- Stability improvements

### 🔧 Technical
- Code refactoring
- Dependency updates

"""
    else:  # patch
        template = f"""## [v{version}] - {date_str}

### 🐛 Bug Fixes
- Critical bug fixes
- Performance optimizations
- Stability improvements

### 🔧 Technical
- Minor code improvements
- Security updates

"""
    
    # Read existing changelog or create new
    existing_content = ""
    if os.path.exists(changelog_file):
        with open(changelog_file, 'r', encoding='utf-8') as f:
            existing_content = f.read()
    
    # Create new content
    if existing_content:
        # Insert after title
        lines = existing_content.split('\n')
        title_line = -1
        for i, line in enumerate(lines):
            if line.startswith('# ') and 'changelog' in line.lower():
                title_line = i
                break
        
        if title_line >= 0:
            new_content = '\n'.join(lines[:title_line+1]) + '\n\n' + template + '\n'.join(lines[title_line+1:])
        else:
            new_content = template + existing_content
    else:
        # Create new changelog
        new_content = f"""# StreamMate AI Changelog

All notable changes to this project will be documented in this file.

{template}"""
    
    with open(changelog_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ Updated {changelog_file}")
    return changelog_file

def git_commit_and_tag(version, changelog_file):
    """Commit changes dan create Git tag"""
    try:
        # Check if git repo
        subprocess.run(["git", "status"], check=True, capture_output=True)
        
        # Add files
        files_to_add = [VERSION_FILE, changelog_file]
        for file_path in files_to_add:
            if os.path.exists(file_path):
                subprocess.run(["git", "add", file_path], check=True)
        
        # Add updated config files
        config_files = ["config/settings.json", "ui/main_window.py"]
        for file_path in config_files:
            if os.path.exists(file_path):
                subprocess.run(["git", "add", file_path], check=True)
        
        # Commit
        commit_message = f"chore: bump version to v{version}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        print(f"✅ Git commit: {commit_message}")
        
        # Create tag
        tag_name = f"v{version}"
        tag_message = f"Release StreamMate AI v{version}"
        subprocess.run(["git", "tag", "-a", tag_name, "-m", tag_message], check=True)
        print(f"✅ Git tag created: {tag_name}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Git operation failed: {e}")
        return False
    except FileNotFoundError:
        print("⚠️  Git not found, skipping Git operations")
        return False

def push_to_remote():
    """Push commits dan tags ke remote"""
    try:
        # Push commits
        subprocess.run(["git", "push"], check=True)
        print("✅ Pushed commits to remote")
        
        # Push tags
        subprocess.run(["git", "push", "--tags"], check=True)
        print("✅ Pushed tags to remote")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Push failed: {e}")
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Bump StreamMate AI version")
    parser.add_argument(
        "bump_type",
        choices=["major", "minor", "patch"],
        help="Type of version bump"
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Skip Git operations"
    )
    parser.add_argument(
        "--no-push",
        action="store_true", 
        help="Skip pushing to remote"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    args = parser.parse_args()
    
    # Get current version
    current_version = get_current_version()
    new_version = bump_version(current_version, args.bump_type)
    
    print("🔄 StreamMate AI Version Bump")
    print("=" * 40)
    print(f"Current version: {current_version}")
    print(f"New version: {new_version}")
    print(f"Bump type: {args.bump_type}")
    print()
    
    if args.dry_run:
        print("🔍 DRY RUN - No changes will be made")
        print("Files that would be updated:")
        print(f"  - {VERSION_FILE}")
        print(f"  - CHANGELOG.md")
        print(f"  - config/settings.json")
        print(f"  - ui/main_window.py")
        if not args.no_git:
            print("Git operations that would be performed:")
            print(f"  - Commit changes")
            print(f"  - Create tag v{new_version}")
            if not args.no_push:
                print(f"  - Push to remote")
        return
    
    # Confirm action
    confirm = input(f"Proceed with version bump to v{new_version}? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Version bump cancelled")
        return
    
    try:
        # Update version file
        update_version_file(new_version)
        
        # Update config files
        update_config_files(new_version)
        
        # Create changelog entry
        changelog_file = create_changelog_entry(new_version, args.bump_type)
        
        # Git operations
        if not args.no_git:
            if git_commit_and_tag(new_version, changelog_file):
                if not args.no_push:
                    if not push_to_remote():
                        print("⚠️  Failed to push to remote, but local changes are saved")
            else:
                print("⚠️  Git operations failed, but version files are updated")
        
        print()
        print("🎉 Version bump completed!")
        print(f"📦 New version: v{new_version}")
        print()
        print("Next steps:")
        print("1. Edit CHANGELOG.md to add detailed release notes")
        print("2. Push changes to trigger GitHub Actions build")
        print("3. Create GitHub release when build completes")
        
    except Exception as e:
        print(f"❌ Error during version bump: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()