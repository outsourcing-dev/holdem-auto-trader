"""
빌드 스크립트 - 홀덤 자동 트레이더 Web Version
Frontend를 빌드하고 PyInstaller로 패키징합니다.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_node():
    """Node.js 설치 확인"""
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print(f"✅ Node.js: {result.stdout.strip()}")
            return True
    except:
        pass
    
    print("❌ Node.js가 설치되어 있지 않습니다.")
    return False

def build_frontend():
    """Frontend 빌드"""
    print("\n📦 Frontend 빌드 중...")
    
    frontend_dir = Path(__file__).parent / 'frontend'
    
    if not frontend_dir.exists():
        print("❌ Frontend 디렉토리를 찾을 수 없습니다.")
        return False
    
    # node_modules 확인 및 설치
    if not (frontend_dir / 'node_modules').exists():
        print("   패키지 설치 중...")
        result = subprocess.run(['npm', 'install'], 
                              cwd=frontend_dir, 
                              shell=True,
                              capture_output=True,
                              text=True)
        if result.returncode != 0:
            print(f"❌ 패키지 설치 실패: {result.stderr}")
            return False
    
    # React 앱 빌드
    print("   React 앱 빌드 중... (시간이 걸릴 수 있습니다)")
    result = subprocess.run(['npm', 'run', 'build'], 
                          cwd=frontend_dir, 
                          shell=True,
                          capture_output=True,
                          text=True)
    
    if result.returncode == 0:
        print("✅ Frontend 빌드 완료")
        return True
    else:
        print(f"❌ Frontend 빌드 실패: {result.stderr}")
        return False

def install_backend_deps():
    """Backend 의존성 설치"""
    print("\n📦 Backend 패키지 설치 중...")
    
    backend_dir = Path(__file__).parent / 'backend'
    req_file = backend_dir / 'requirements.txt'
    
    if not req_file.exists():
        print("❌ requirements.txt를 찾을 수 없습니다.")
        return False
    
    result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(req_file)],
                          capture_output=True,
                          text=True)
    
    if result.returncode == 0:
        print("✅ Backend 패키지 설치 완료")
        return True
    else:
        print(f"❌ Backend 패키지 설치 실패: {result.stderr}")
        return False

def copy_database():
    """기존 데이터베이스 복사"""
    parent_db = Path(__file__).parent.parent / 'user_accounts.db'
    target_db = Path(__file__).parent / 'user_accounts.db'
    
    if parent_db.exists() and not target_db.exists():
        shutil.copy2(parent_db, target_db)
        print("✅ 데이터베이스 복사 완료")

def build_executable():
    """PyInstaller로 실행 파일 빌드"""
    print("\n🔨 실행 파일 빌드 중...")
    
    spec_file = Path(__file__).parent / 'build.spec'
    
    if not spec_file.exists():
        print("❌ build.spec 파일을 찾을 수 없습니다.")
        return False
    
    # PyInstaller 실행
    result = subprocess.run(['pyinstaller', '--clean', '--noconfirm', str(spec_file)],
                          capture_output=True,
                          text=True)
    
    if result.returncode == 0:
        print("✅ 실행 파일 빌드 완료")
        
        # 결과 파일 확인
        dist_dir = Path(__file__).parent / 'dist'
        exe_file = dist_dir / 'HoldemAutoTrader_Web.exe'
        
        if exe_file.exists():
            print(f"\n✨ 빌드 완료!")
            print(f"   실행 파일: {exe_file}")
            print(f"   파일 크기: {exe_file.stat().st_size / 1024 / 1024:.2f} MB")
            return True
        else:
            print("❌ 실행 파일이 생성되지 않았습니다.")
            return False
    else:
        print(f"❌ PyInstaller 빌드 실패: {result.stderr}")
        return False

def clean_build_files():
    """빌드 임시 파일 정리"""
    print("\n🧹 임시 파일 정리 중...")
    
    dirs_to_clean = ['build', '__pycache__']
    
    for dir_name in dirs_to_clean:
        dir_path = Path(__file__).parent / dir_name
        if dir_path.exists():
            shutil.rmtree(dir_path)
    
    print("✅ 정리 완료")

def main():
    """메인 빌드 프로세스"""
    print("="*60)
    print("🔨 홀덤 자동 트레이더 Web Version 빌드")
    print("="*60)
    
    # Node.js 확인
    if not check_node():
        print("\n먼저 Node.js를 설치해주세요: https://nodejs.org")
        return 1
    
    # PyInstaller 확인
    try:
        import PyInstaller
        print(f"✅ PyInstaller: {PyInstaller.__version__}")
    except ImportError:
        print("❌ PyInstaller가 설치되어 있지 않습니다.")
        print("   설치: pip install pyinstaller")
        return 1
    
    # Backend 의존성 설치
    if not install_backend_deps():
        return 1
    
    # Frontend 빌드
    if not build_frontend():
        return 1
    
    # 데이터베이스 복사
    copy_database()
    
    # 실행 파일 빌드
    if not build_executable():
        return 1
    
    # 정리
    if '--clean' in sys.argv:
        clean_build_files()
    
    print("\n" + "="*60)
    print("✅ 모든 빌드 과정이 완료되었습니다!")
    print("   dist/HoldemAutoTrader_Web.exe 파일을 배포하세요.")
    print("="*60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())