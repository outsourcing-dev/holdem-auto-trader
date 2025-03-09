# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# 현재 디렉토리 (spec 파일이 있는 위치)
current_dir = os.path.dirname(os.path.abspath(SPEC))

# 모든 하위 디렉토리를 추가할 폴더 목록
include_folders = ['ui', 'utils', 'services', 'modules', 'db']

# 설정 파일들을 루트 디렉토리에 명시적으로 추가
datas = [
    ('README.md', '.'),
    ('settings.json', '.'),
    ('room_settings.json', '.'),
    ('AUTO.encrypted', '.'),
    ('ui/style.qss', 'ui'),
    ('db/users.db', 'db')
]

# 각 폴더 내의 모든 파일 추가
for folder in include_folders:
    folder_path = os.path.join(current_dir, folder)
    if os.path.exists(folder_path):
        for dirpath, dirnames, filenames in os.walk(folder_path):
            rel_path = os.path.relpath(dirpath, current_dir)
            for filename in filenames:
                if filename.endswith('.py') or filename.endswith('.json') or filename.endswith('.qss'):
                    source_path = os.path.join(dirpath, filename)
                    target_path = rel_path
                    # datas 리스트에 추가 (중복 방지)
                    if (source_path, target_path) not in datas:
                        datas.append((source_path, target_path))

# 필요한 모듈 가져오기
hidden_imports = [
    'PyQt6.QtSvg',
    'PyQt6.QtXml',
    'PyQt6.QtSvgWidgets',
    'PyQt6.QtNetwork',
    'PyQt6.QtPrintSupport',
    'PyQt6.sip',
    'win32com',
    'win32com.client',
    'pythoncom',
    'openpyxl',
    'openpyxl.cell',
    'openpyxl.utils',
    'openpyxl.styles',
    'undetected_chromedriver',
    'selenium',
    'bs4',
    'pandas',
    'numpy',
    'psutil',
    'websockets',
    'urllib3',
    'json',
    're',
    'random',
    'time',
    'logging',
    'pymysql'
]

# 폴더 내의 모든 모듈 자동 추가
for folder in include_folders:
    if os.path.exists(os.path.join(current_dir, folder)):
        for py_file in os.listdir(os.path.join(current_dir, folder)):
            if py_file.endswith('.py') and py_file != '__init__.py':
                module_name = f'{folder}.{py_file[:-3]}'
                if module_name not in hidden_imports:
                    hidden_imports.append(module_name)

# 유틸리티 모듈에서 submodule 수집
hidden_imports.extend(collect_submodules('utils'))
hidden_imports.extend(collect_submodules('services'))
hidden_imports.extend(collect_submodules('modules'))

a = Analysis(
    ['main.py'],
    pathex=[current_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 중복 제거
a.datas = list(set(a.datas))

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='holdem_auto_trader',  # 영문 이름으로 변경
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon 항목 제거 (아이콘 파일이 없는 경우)
    # version='file_version_info.txt',  # 버전 정보 파일 (있는 경우)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='holdem_auto_trader',  # 영문 이름으로 변경
)