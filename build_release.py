#!/usr/bin/env python3
"""
Umi-OCR Release 打包脚本
功能：自动打包完整发布包，排除敏感文件和临时文件
用法：python build_release.py
"""

import os
import json
import shutil
import subprocess
import sys
import fnmatch
from pathlib import Path

try:
    import ctypes
except ImportError:
    ctypes = None

# ==================== 配置区 ====================

PROJECT_NAME = "Umi-OCR"
ABOUT_PATH = Path("UmiOCR-data") / "about.json"
RELEASE_PLUGIN_NAMES = (
    "AIOCR",
    "win7_x64_PaddleOCR-json_PP-OCRv5",
)
DEFAULT_OCR_PLUGIN_KEY = "win7_x64_PaddleOCR-json_PP-OCRv5"
DEFAULT_OCR_PLUGIN = Path("UmiOCR-data") / "plugins" / DEFAULT_OCR_PLUGIN_KEY

EXCLUDE_PATTERNS = [
    ".settings",
    ".pre_settings",
    "__pycache__",
    "*.pyc",
    "logs",
    "temp",
    "temp_doc",
    "*.log",
    ".git",
    ".github",
    ".vscode",
    "dev-tools",
    "docs",
    "build",
    "release",
    "diff.md",
    "CHANGE_LOG.md",
    "build_release.py",
    "*.md",
    "README*.md",
]

# ==================== 核心逻辑 ====================

def get_project_root():
    return Path(__file__).parent.resolve()


def show_popup(title, message, level="info"):
    if os.name != "nt" or ctypes is None:
        return

    flags = {
        "info": 0x40,
        "warning": 0x30,
        "error": 0x10,
    }.get(level, 0x40)

    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, flags)
    except Exception:
        pass


def fail(message, exit_code=1):
    print(f"\n[错误] {message}")
    show_popup(f"{PROJECT_NAME} Release 打包失败", message, "error")
    sys.exit(exit_code)


def get_version(project_root):
    about_path = project_root / ABOUT_PATH
    if not about_path.exists():
        fail(f"未找到版本文件：{about_path}")

    try:
        with open(about_path, "r", encoding="utf-8") as file:
            about = json.load(file)
    except Exception as exc:
        fail(f"读取版本文件失败：{about_path}\n{exc}")

    version = about.get("version", {})
    major = version.get("major")
    minor = version.get("minor")
    patch = version.get("patch")
    if major is None or minor is None or patch is None:
        fail(f"版本文件缺少必要字段：{about_path}")

    version_text = f"{major}.{minor}.{patch}"
    prerelease = version.get("prerelease")
    prerelease_number = version.get("prereleaseNumber", 0)
    if prerelease:
        version_text += f"-{prerelease}.{prerelease_number}"
    return version_text


def validate_release_inputs(project_root):
    required_paths = [
        (project_root / "Umi-OCR.exe", "未找到 Umi-OCR.exe，无法生成可运行的发布包。"),
        (project_root / "UmiOCR-data", "未找到 UmiOCR-data 目录。"),
        (project_root / ABOUT_PATH, "未找到 about.json，无法读取版本号。"),
        (project_root / DEFAULT_OCR_PLUGIN, f"未找到默认 OCR 插件 {DEFAULT_OCR_PLUGIN_KEY}；当前默认接口将不可用。"),
    ]
    for plugin_name in RELEASE_PLUGIN_NAMES:
        required_paths.append(
            (
                project_root / "UmiOCR-data" / "plugins" / plugin_name,
                f"未找到发布插件 {plugin_name}。",
            )
        )
    for path, message in required_paths:
        if not path.exists():
            fail(message)


def should_exclude_plugin(file_path, project_root):
    rel_path = file_path.relative_to(project_root)
    parts = rel_path.parts
    if len(parts) >= 3 and parts[0] == "UmiOCR-data" and parts[1] == "plugins":
        return parts[2] not in RELEASE_PLUGIN_NAMES
    return False


def should_exclude(file_path, project_root):
    rel_path = file_path.relative_to(project_root)
    rel_str = str(rel_path).replace("\\", "/")
    name = file_path.name
    
    for pattern in EXCLUDE_PATTERNS:
        if name == pattern:
            return True
        if "*" in pattern:
            if fnmatch.fnmatch(name, pattern):
                return True
        if f"/{pattern}/" in f"/{rel_str}/":
            return True
    
    return False

def copy_tree(src, dst, project_root):
    os.makedirs(dst, exist_ok=True)
    
    for item in os.listdir(src):
        s = src / item
        d = dst / item

        if should_exclude_plugin(s, project_root):
            print(f"  [排除插件] {s.relative_to(project_root)}")
            continue
        
        if should_exclude(s, project_root):
            print(f"  [排除] {s.relative_to(project_root)}")
            continue
        
        if s.is_dir():
            copy_tree(s, d, project_root)
        else:
            shutil.copy2(s, d)

def create_7z(source_dir, output_file):
    seven_zip_paths = [
        "7z",
        "7z.exe",
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ]
    
    seven_zip = None
    for path in seven_zip_paths:
        try:
            subprocess.run([path, "--help"], capture_output=True, timeout=5)
            seven_zip = path
            break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    if not seven_zip:
        message = (
            "未找到 7-Zip，已生成目录版发布包，但未生成 7z 压缩包。\n"
            "请安装 7-Zip: https://www.7-zip.org/\n"
            f"打包目录: {source_dir}"
        )
        print(f"\n[警告] {message}")
        return False, message
    
    print(f"\n正在压缩: {output_file}")
    cmd = [
        seven_zip, "a",
        "-t7z",
        "-mx=9",
        output_file,
        str(source_dir) + "\\*",
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        print(f"[成功] 压缩包: {output_file} ({size_mb:.2f} MB)")
        return True, ""
    else:
        error_text = result.stderr.strip() or result.stdout.strip() or "未知错误"
        message = f"7z 压缩失败：{error_text}"
        print(f"[失败] {message}")
        return False, message

def main():
    project_root = get_project_root()
    os.chdir(project_root)
    validate_release_inputs(project_root)
    version = get_version(project_root)
    
    output_name = f"{PROJECT_NAME}-v{version}"
    build_dir = project_root / "release" / output_name
    output_7z = project_root / "release" / f"{output_name}.7z"
    warnings = []
    
    if build_dir.exists():
        print(f"清理旧构建: {build_dir}")
        shutil.rmtree(build_dir)
    if output_7z.exists():
        output_7z.unlink()
    
    os.makedirs(build_dir, exist_ok=True)
    
    print(f"{'='*50}")
    print(f"  {PROJECT_NAME} v{version} - 打包开始")
    print(f"  插件白名单: {', '.join(RELEASE_PLUGIN_NAMES)}")
    print(f"{'='*50}")
    
    exe_src = project_root / "Umi-OCR.exe"
    print(f"\n[复制] Umi-OCR.exe")
    shutil.copy2(exe_src, build_dir / "Umi-OCR.exe")

    license_src = project_root / "LICENSE"
    if license_src.exists():
        print(f"\n[复制] LICENSE")
        shutil.copy2(license_src, build_dir / "LICENSE")
    else:
        warnings.append("未找到 LICENSE，发布包未包含许可证文件。")
    
    data_src = project_root / "UmiOCR-data"
    print(f"\n[复制] UmiOCR-data/")
    copy_tree(data_src, build_dir / "UmiOCR-data", project_root)
    
    print(f"\n{'='*50}")
    _, archive_message = create_7z(build_dir, str(output_7z))
    if archive_message:
        warnings.append(archive_message)
    
    print(f"\n{'='*50}")
    print(f"  打包完成！")
    print(f"  输出目录: {build_dir}")
    print(f"  输出文件: {output_7z}")
    print(f"{'='*50}")

    if warnings:
        show_popup(f"{PROJECT_NAME} Release 打包完成（有警告）", "\n\n".join(warnings), "warning")

if __name__ == "__main__":
    main()
