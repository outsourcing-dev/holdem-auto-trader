"""
독립 프로세스로 브라우저 실행
"""
import sys
import time
from playwright.sync_api import sync_playwright

def launch_browser(site_url: str):
    """브라우저를 독립 프로세스에서 실행"""
    print(f"Launching browser to: {site_url}")
    
    p = sync_playwright().start()
    
    # 브라우저 실행 시 보안 설정 완화
    browser = p.chromium.launch(
        headless=False,
        args=[
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-site-isolation-trials',
            '--disable-blink-features=AutomationControlled',
            '--allow-running-insecure-content',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--single-process',
            '--disable-gpu'
        ]
    )
    
    # 컨텍스트 생성 시 권한 부여
    context = browser.new_context(
        ignore_https_errors=True,
        permissions=['geolocation', 'notifications'],
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
    )
    
    page = context.new_page()
    
    # JavaScript 실행 가능하도록 설정
    page.add_init_script("""
        // iframe 접근 허용
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Chrome 자동화 감지 우회
        window.chrome = {
            runtime: {}
        };
        
        // 권한 관련 설정
        Object.defineProperty(navigator, 'permissions', {
            get: () => ({
                query: () => Promise.resolve({ state: 'granted' })
            })
        });
    """)
    
    page.goto(site_url)
    
    print("Browser launched successfully")
    
    # 브라우저가 열린 상태 유지
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        browser.close()
        p.stop()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        launch_browser(sys.argv[1])
    else:
        print("Usage: python browser_launcher.py <site_url>")