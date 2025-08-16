"""
Selenium과 undetected-chromedriver를 사용한 브라우저 실행
Evolution Gaming iframe 접근 문제 해결용
"""
import sys
import time
import undetected_chromedriver as uc

def launch_browser(site_url: str):
    """undetected-chromedriver로 브라우저 실행"""
    print(f"Launching browser with undetected-chromedriver to: {site_url}")
    
    # Chrome 옵션 설정 - 최소한의 옵션만 사용
    options = uc.ChromeOptions()
    
    # 기본 설정
    options.add_argument('--start-maximized')
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    # 보안 설정 완화 (iframe 접근용)
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-site-isolation-trials')
    
    # undetected-chromedriver 실행
    driver = uc.Chrome(options=options, use_subprocess=True)
    
    # JavaScript로 자동화 감지 우회
    driver.execute_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        
        Object.defineProperty(navigator, 'languages', {
            get: () => ['ko-KR', 'ko', 'en-US', 'en']
        });
        
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        
        Object.defineProperty(navigator, 'permissions', {
            get: () => ({
                query: () => Promise.resolve({ state: 'granted' })
            })
        });
    """)
    
    # 사이트로 이동
    driver.get(site_url)
    
    print("Browser launched successfully with undetected-chromedriver")
    
    # 브라우저가 열린 상태 유지
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        driver.quit()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        launch_browser(sys.argv[1])
    else:
        print("Usage: python browser_launcher_selenium.py <site_url>")