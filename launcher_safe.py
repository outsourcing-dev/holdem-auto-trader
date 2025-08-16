"""
홀덤 웹 트레이더 안전한 런처
기존 서버를 종료하고 새로 시작합니다.
"""
import os
import sys
import time
import socket
import signal
import psutil
import webbrowser
import subprocess
import threading
from pathlib import Path

def kill_process_on_port(port):
    """특정 포트를 사용하는 프로세스 종료"""
    try:
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN':
                try:
                    process = psutil.Process(conn.pid)
                    print(f"포트 {port}을 사용하는 프로세스 종료: PID {conn.pid}")
                    process.terminate()
                    time.sleep(1)
                    if process.is_running():
                        process.kill()
                except:
                    pass
    except Exception as e:
        print(f"프로세스 종료 중 오류: {e}")

def is_port_open(port):
    """포트가 열려 있는지 확인"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', port))
    sock.close()
    return result == 0

def open_browser():
    """브라우저 열기"""
    # 서버가 완전히 시작될 때까지 대기
    for i in range(10):
        if is_port_open(8000):
            print("서버가 시작되었습니다. 브라우저를 엽니다...")
            webbrowser.open("http://localhost:8000")
            return
        time.sleep(1)
    print("서버 시작 실패")

def run_server():
    """백엔드 서버 실행"""
    # 현재 디렉토리 설정
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys._MEIPASS)
    else:
        base_dir = Path(__file__).parent
    
    backend_dir = base_dir / "backend"
    
    # main.py 경로
    main_py = backend_dir / "main.py"
    
    if not main_py.exists():
        print(f"main.py를 찾을 수 없습니다: {main_py}")
        input("Enter를 눌러 종료...")
        return
    
    # Python으로 main.py 실행
    os.chdir(backend_dir)
    subprocess.run([sys.executable, "main.py"])

def signal_handler(sig, frame):
    """Ctrl+C 시그널 처리"""
    print("\n프로그램을 종료합니다...")
    kill_process_on_port(8000)
    sys.exit(0)

def main():
    print("=" * 60)
    print("홀덤 자동 트레이더 웹 서버")
    print("=" * 60)
    
    # Ctrl+C 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    
    # 기존 서버 종료
    if is_port_open(8000):
        print("기존 서버를 종료합니다...")
        kill_process_on_port(8000)
        time.sleep(2)
    
    print("새 서버를 시작합니다...")
    
    # 브라우저 열기 스레드
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    try:
        # 서버 실행
        run_server()
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다...")
    finally:
        # 종료 시 서버 프로세스 정리
        kill_process_on_port(8000)

if __name__ == "__main__":
    main()