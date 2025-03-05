import undetected_chromedriver as uc
import time
import os
import re
import subprocess
import platform

class DevToolsController:
    def __init__(self):
        self.driver = None  # 초기에는 브라우저 실행 X

    def get_chrome_version(self):
        """현재 시스템에 설치된 Chrome 브라우저의 버전을 감지"""
        version = None
        system = platform.system()
        
        try:
            if system == "Windows":
                # Windows에서 Chrome 레지스트리 경로
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Google\Chrome\BLBeacon')
                version, _ = winreg.QueryValueEx(key, 'version')
            
            elif system == "Darwin":  # macOS
                process = subprocess.Popen(
                    ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--version'],
                    stdout=subprocess.PIPE
                )
                version = process.communicate()[0].decode('UTF-8').replace('Google Chrome', '').strip()
            
            elif system == "Linux":
                process = subprocess.Popen(
                    ['google-chrome', '--version'],
                    stdout=subprocess.PIPE
                )
                version = process.communicate()[0].decode('UTF-8').replace('Google Chrome', '').strip()
            
            # 버전에서 메이저 버전 추출 (예: "92.0.4515.107" -> 92)
            if version:
                version_match = re.search(r'(\d+)\.', version)
                if version_match:
                    return int(version_match.group(1))
        
        except Exception as e:
            print(f"[WARNING] Chrome 버전 감지 중 오류 발생: {e}")
            print("[INFO] 기본 ChromeDriver 사용")
        
        return None  # 버전을 감지할 수 없는 경우

    def start_browser(self):
        """Chrome 브라우저 실행 (버튼 클릭 시 실행)"""
        if self.driver is None:  # 브라우저가 실행되지 않았을 때만 실행
            options = uc.ChromeOptions()
            options.headless = False  # False: UI 보이게, True: 백그라운드 실행
            options.add_argument("--disable-blink-features=AutomationControlled")  # 봇 탐지 우회
            
            # Chrome 버전 감지 및 적용
            chrome_version = self.get_chrome_version()
            if chrome_version:
                print(f"[INFO] 감지된 Chrome 버전: {chrome_version}")
                try:
                    self.driver = uc.Chrome(options=options, version_main=chrome_version)
                    print(f"[INFO] Chrome {chrome_version} 버전용 드라이버로 브라우저 실행됨")
                except Exception as e:
                    print(f"[ERROR] 특정 버전 ChromeDriver 실행 실패: {e}")
                    print("[INFO] 기본 설정으로 재시도 중...")
                    self.driver = uc.Chrome(options=options)
            else:
                # 버전 감지 실패 시 기본 설정 사용
                self.driver = uc.Chrome(options=options)
                print("[INFO] 기본 설정으로 Chrome 브라우저 실행됨")
            
            print("[INFO] Chrome 브라우저 실행 완료")
        else:
            print("[INFO] 이미 실행 중인 Chrome 브라우저가 있음")

    def open_site(self, url):
        """버튼을 눌렀을 때만 브라우저를 실행하고 사이트 이동"""
        if not self.driver:
            print("[INFO] 브라우저가 실행되지 않아 start_browser() 호출")
            self.start_browser()

        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        print(f"[INFO] 사이트 이동: {url}")
        self.driver.get(url)
        time.sleep(3)  # 페이지 로딩 대기

    def get_page_source(self):
        """현재 페이지의 HTML 가져오기"""
        if not self.driver:
            print("[ERROR] 브라우저가 실행되지 않음")
            return None
        return self.driver.page_source  # HTML 반환

    def close_browser(self):
        """브라우저 종료"""
        if self.driver:
            self.driver.quit()
            self.driver = None  # 종료 후 드라이버 변수 초기화
            print("[INFO] 브라우저 종료됨")

    def get_redirected_url(self):
        """현재 브라우저의 URL을 가져오는 함수"""
        if not self.driver:
            print("[ERROR] WebDriver가 실행되지 않음")
            return None
        return self.driver.current_url  # 현재 URL 반환