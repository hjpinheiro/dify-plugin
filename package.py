#!/usr/bin/env python3
import os
import zipfile

def create_package():
    include_items = [
        'manifest.yaml',
        'provider/',
        'tools/',
        '_assets/',
        'requirements.txt',
        'main.py',
        '_client.py',
        'PRIVACY.md',
    ]

    exclude_patterns = [
        '__pycache__',
        '.pyc',
        '.env',
        '.git',
        '.DS_Store',
        'pyproject.toml',
        'uv.lock',
        '.difyignore',
        'package.py',
    ]

    with zipfile.ZipFile('daytona.difypkg', 'w', zipfile.ZIP_DEFLATED) as zipf:
        for item in include_items:
            if os.path.isfile(item) and not any(p in item for p in exclude_patterns):
                zipf.write(item)
            elif os.path.isdir(item):
                for root, dirs, files in os.walk(item):
                    dirs[:] = [d for d in dirs if not any(p in d for p in exclude_patterns)]
                    for file in files:
                        if not any(p in file for p in exclude_patterns):
                            file_path = os.path.join(root, file)
                            zipf.write(file_path)

    print(f"Done: {os.path.getsize('daytona.difypkg') / 1024:.2f} KB")

if __name__ == '__main__':
    create_package()
