"""
홀덤 웹 트레이더 간단한 런처
"""
import os
import sys
import time
import webbrowser
import subprocess
import threading
from pathlib import Path

def run_server():
    """백엔드 서버 실행"""
    # 현재 디렉토리 설정
    if getattr(sys, 'frozen', False):
        # 실행파일로 실행된 경우
        base_dir = Path(sys._MEIPASS)
    else:
        # Python으로 실행된 경우
        base_dir = Path(__file__).parent
    
    backend_dir = base_dir / "backend"
    os.chdir(backend_dir)
    
    # Python 경로 찾기
    python_exe = sys.executable
    
    # main.py 실행
    subprocess.run([python_exe, "main.py"])

def open_browser():
    """브라우저 열기"""
    time.sleep(3)
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    print("=" * 60)
    print("홀덤 자동 트레이더 웹 서버를 시작합니다...")
    print("브라우저가 자동으로 열립니다...")
    print("=" * 60)
    
    # 브라우저 열기 스레드
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # 서버 실행
    run_server()