"""
직접 Chrome 실행하는 간단한 런처
"""
import sys
import os
import time

def launch_browser(site_url: str):
    """Chrome을 직접 실행"""
    import subprocess
    
    print(f"브라우저 실행 시도: {site_url}", flush=True)
    
    # Chrome 경로
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    
    chrome_exe = None
    for path in chrome_paths:
        if os.path.exists(path):
            chrome_exe = path
            break
    
    if not chrome_exe:
        print("Chrome을 찾을 수 없습니다", flush=True)
        # Edge로 폴백
        edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if os.path.exists(edge_path):
            chrome_exe = edge_path
            print(f"Edge 사용: {edge_path}", flush=True)
        else:
            print("브라우저를 찾을 수 없습니다", flush=True)
            return
    
    # 브라우저 실행 명령
    cmd = [chrome_exe, "--new-window", site_url]
    
    print(f"실행 명령: {' '.join(cmd)}", flush=True)
    
    # 브라우저 프로세스 시작
    try:
        process = subprocess.Popen(cmd, 
                                 stdout=subprocess.DEVNULL, 
                                 stderr=subprocess.DEVNULL)
        print(f"브라우저 프로세스 시작됨 (PID: {process.pid})", flush=True)
    except Exception as e:
        print(f"브라우저 실행 실패: {e}", flush=True)
        return
    
    # 프로세스 유지
    print("브라우저 런처 실행 중...", flush=True)
    sys.stdout.flush()
    
    while True:
        time.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        site_url = sys.argv[1]
        launch_browser(site_url)
    else:
        print("Usage: python browser_launcher_direct.py <url>")