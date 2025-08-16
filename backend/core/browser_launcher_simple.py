"""
Simple Selenium browser launcher - 기본 Chrome driver 사용
브라우저가 실제로 열리는지 테스트용
"""
import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def launch_browser(site_url: str):
    """기본 Chrome WebDriver로 브라우저 실행"""
    print(f"Launching browser with Selenium to: {site_url}")
    
    # Chrome 옵션 설정
    options = Options()
    
    # 기본 설정
    options.add_argument('--start-maximized')
    
    # 보안 설정 완화 (iframe 접근용)
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-site-isolation-trials')
    options.add_argument('--allow-running-insecure-content')
    
    # Chrome driver 실행
    driver = webdriver.Chrome(options=options)
    
    # 사이트로 이동
    driver.get(site_url)
    
    print("Browser launched successfully with Selenium")
    
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
        print("Usage: python browser_launcher_simple.py <site_url>")