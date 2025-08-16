"""
시스템 기본 브라우저를 사용한 간단한 브라우저 실행
"""
import sys
import time
import subprocess
import os

def launch_browser(site_url: str):
    """Chrome 브라우저로 직접 실행"""
    print(f"Opening {site_url} in Chrome browser...", flush=True)
    
    # Chrome 경로 찾기
    chrome_path = None
    possible_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            chrome_path = path
            print(f"Found Chrome at: {path}", flush=True)
            break
    
    if chrome_path:
        # Chrome을 subprocess로 직접 실행
        try:
            # 새 창으로 열기
            subprocess.Popen([chrome_path, "--new-window", site_url])
            print(f"Chrome launched successfully with URL: {site_url}", flush=True)
        except Exception as e:
            print(f"Failed to launch Chrome: {e}", flush=True)
            # 폴백: 기본 브라우저로 열기
            import webbrowser
            webbrowser.open_new_tab(site_url)
            print("Opened in default browser as fallback", flush=True)
    else:
        # Chrome이 없으면 기본 브라우저로 열기
        print("Chrome not found, using default browser", flush=True)
        import webbrowser
        webbrowser.open_new_tab(site_url)
        print("Opened in default browser", flush=True)
    
    # 브라우저가 열린 상태 유지
    print("Browser launcher running. Process will keep running...", flush=True)
    sys.stdout.flush()  # 출력 버퍼 강제 플러시
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Browser launcher stopped")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        launch_browser(sys.argv[1])
    else:
        print("Usage: python browser_launcher_system.py <site_url>")