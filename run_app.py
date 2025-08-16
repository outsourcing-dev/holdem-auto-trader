"""
홀덤 자동 트레이더 Web 통합 실행 스크립트
Frontend와 Backend를 함께 실행합니다.
"""
import os
import sys
import subprocess
import time
import webbrowser
import signal
import psutil
from pathlib import Path

# 프로세스 목록
processes = []

def kill_process_tree(pid):
    """프로세스와 모든 자식 프로세스를 종료"""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        # 자식 프로세스 먼저 종료
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        
        # 부모 프로세스 종료
        try:
            parent.terminate()
        except psutil.NoSuchProcess:
            pass
            
        # 강제 종료
        gone, still_alive = psutil.wait_procs(children + [parent], timeout=3)
        for p in still_alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
                
    except psutil.NoSuchProcess:
        pass

def cleanup():
    """모든 실행 중인 프로세스 정리"""
    print("\n애플리케이션 종료 중...")
    
    for process in processes:
        try:
            if process.poll() is None:
                kill_process_tree(process.pid)
        except:
            pass
    
    print("모든 프로세스가 종료되었습니다.")
    sys.exit(0)

def signal_handler(sig, frame):
    """Ctrl+C 시그널 핸들러"""
    cleanup()

def check_node_installed():
    """Node.js 설치 확인"""
    try:
        result = subprocess.run(['node', '--version'], 
                              capture_output=True, 
                              text=True, 
                              shell=True)
        if result.returncode == 0:
            print(f"Node.js 감지됨: {result.stdout.strip()}")
            return True
    except:
        pass
    
    print("Node.js가 설치되어 있지 않습니다.")
    print("   Node.js를 먼저 설치해주세요: https://nodejs.org")
    return False

def install_dependencies():
    """필요한 패키지 설치"""
    print("\n의존성 패키지 설치 중...")
    
    # Backend 패키지 설치
    backend_dir = Path(__file__).parent / 'backend'
    if backend_dir.exists():
        print("   Backend 패키지 설치 중...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 
                       str(backend_dir / 'requirements.txt')], 
                      check=False)
    
    # Frontend 패키지 설치
    frontend_dir = Path(__file__).parent / 'frontend'
    if frontend_dir.exists() and check_node_installed():
        print("   Frontend 패키지 설치 중...")
        os.chdir(frontend_dir)
        
        # package-lock.json이 있으면 ci 사용, 없으면 install 사용
        if (frontend_dir / 'package-lock.json').exists():
            subprocess.run(['npm', 'ci'], shell=True, check=False)
        else:
            subprocess.run(['npm', 'install'], shell=True, check=False)
        
        os.chdir(Path(__file__).parent)

def start_backend():
    """Backend 서버 시작"""
    print("\nBackend 서버 시작 중...")
    
    backend_dir = Path(__file__).parent / 'backend'
    if not backend_dir.exists():
        print("Backend 디렉토리를 찾을 수 없습니다.")
        return None
    
    # FastAPI 서버 실행
    process = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'main:app', '--reload', '--port', '8000'],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True
    )
    
    # 서버 시작 대기
    time.sleep(3)
    
    if process.poll() is None:
        print("Backend 서버가 시작되었습니다. (http://localhost:8000)")
        return process
    else:
        print("Backend 서버 시작 실패")
        return None

def start_frontend():
    """Frontend 개발 서버 시작"""
    print("\nFrontend 서버 시작 중...")
    
    frontend_dir = Path(__file__).parent / 'frontend'
    if not frontend_dir.exists():
        print("Frontend 디렉토리를 찾을 수 없습니다.")
        return None
    
    if not check_node_installed():
        return None
    
    # React 개발 서버 실행
    env = os.environ.copy()
    env['BROWSER'] = 'none'  # 자동으로 브라우저 열지 않음
    
    process = subprocess.Popen(
        ['npm', 'start'],
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        env=env
    )
    
    # 서버 시작 대기
    print("   React 앱 컴파일 중... (최초 실행 시 시간이 걸릴 수 있습니다)")
    time.sleep(10)
    
    if process.poll() is None:
        print("Frontend 서버가 시작되었습니다. (http://localhost:3000)")
        return process
    else:
        print("Frontend 서버 시작 실패")
        return None

def main():
    """메인 실행 함수"""
    print("="*60)
    print("홀덤 자동 트레이더 Web Version 2.0")
    print("="*60)
    
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 의존성 설치 (최초 실행 시)
    if '--install' in sys.argv or not (Path(__file__).parent / 'frontend' / 'node_modules').exists():
        install_dependencies()
    
    # Backend 시작
    backend_process = start_backend()
    if backend_process:
        processes.append(backend_process)
    else:
        print("Backend 서버를 시작할 수 없습니다.")
        cleanup()
        return
    
    # Frontend 시작
    frontend_process = start_frontend()
    if frontend_process:
        processes.append(frontend_process)
    else:
        print("Frontend 서버를 시작할 수 없습니다.")
        cleanup()
        return
    
    # 브라우저 열기
    time.sleep(2)
    print("\n웹 브라우저에서 애플리케이션을 여는 중...")
    webbrowser.open('http://localhost:3000')
    
    print("\n" + "="*60)
    print("애플리케이션이 실행 중입니다!")
    print("   Frontend: http://localhost:3000")
    print("   Backend API: http://localhost:8000")
    print("   API 문서: http://localhost:8000/docs")
    print("\n종료하려면 Ctrl+C를 누르세요.")
    print("="*60)
    
    # 프로세스 모니터링
    try:
        while True:
            # 프로세스 상태 확인
            for i, process in enumerate(processes):
                if process.poll() is not None:
                    if i == 0:
                        print("\nBackend 서버가 종료되었습니다.")
                    else:
                        print("\nFrontend 서버가 종료되었습니다.")
                    cleanup()
                    return
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()