#!/usr/bin/env python3
import glob
import os
import sys
import zipfile

import yaml


def _fail(msg):
    print(f"PACKAGING ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def validate():
    yaml_files = ["manifest.yaml"] + glob.glob("provider/*.yaml") + glob.glob("tools/*.yaml")
    for f in yaml_files:
        if not os.path.isfile(f):
            _fail(f"Missing YAML file: {f}")
        try:
            with open(f, "r", encoding="utf-8") as fh:
                yaml.safe_load(fh)
        except yaml.YAMLError as e:
            _fail(f"YAML parse error in {f}: {e}")

    with open("manifest.yaml", "r", encoding="utf-8") as fh:
        manifest = yaml.safe_load(fh)
    top_version = manifest.get("version")
    meta = manifest.get("meta") or {}
    meta_version = meta.get("version")
    if not top_version:
        _fail("manifest.yaml missing top-level 'version'")
    if not meta_version:
        _fail("manifest.yaml missing 'meta.version'")
    if top_version != meta_version:
        _fail(f"manifest.yaml version mismatch: top-level={top_version}, meta={meta_version}")

    with open("provider/daytona.yaml", "r", encoding="utf-8") as fh:
        provider = yaml.safe_load(fh)
    tool_paths = provider.get("tools") or []
    for tp in tool_paths:
        if not os.path.isfile(tp):
            _fail(f"Registered tool YAML not found: {tp}")
        tool_name = os.path.basename(tp).replace(".yaml", "")
        py_path = f"tools/{tool_name}.py"
        if not os.path.isfile(py_path):
            _fail(f"Tool Python source not found for '{tool_name}': {py_path}")


def create_package():
    validate()

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

    with zipfile.ZipFile('daytona.difypkg', 'r') as zipf:
        for info in zipf.infolist():
            if info.is_dir():
                _fail(f"Directory entry found in archive: {info.filename}")

    print(f"Done: {os.path.getsize('daytona.difypkg') / 1024:.2f} KB")


if __name__ == '__main__':
    create_package()
