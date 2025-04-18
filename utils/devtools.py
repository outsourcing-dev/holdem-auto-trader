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
        """Chrome 브라우저 실행 (버튼 클릭 시 실행) - 에러 처리 강화"""
        # 이미 실행 중인 경우 먼저 닫기
        if self.driver:
            try:
                self.close_browser()
                time.sleep(1)  # 브라우저가 완전히 종료될 때까지 대기
            except Exception as e:
                print(f"[WARNING] 기존 브라우저 종료 실패: {e}")
                self.driver = None  # 참조 초기화
        
        try:
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
            return True
        except Exception as e:
            print(f"[ERROR] 브라우저 시작 실패: {e}")
            self.driver = None
            return False

    def open_site(self, url):
        """버튼을 눌렀을 때만 브라우저를 실행하고 사이트 이동 - 에러 처리 강화"""
        try:
            # 브라우저가 없거나 실행 중이 아니면 새로 시작
            if not self.driver:
                print("[INFO] 브라우저가 실행되지 않아 start_browser() 호출")
                start_success = self.start_browser()
                if not start_success:
                    print("[ERROR] 브라우저 시작 실패")
                    return False

            # URL 형식 검증 및 수정
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url

            print(f"[INFO] 사이트 이동: {url}")
            try:
                self.driver.get(url)
            except Exception as e:
                print(f"[ERROR] 페이지 이동 중 오류 발생: {e}")
                # 브라우저가 응답하지 않으면 재시작 시도
                print("[INFO] 브라우저 재시작 시도...")
                self.close_browser()
                time.sleep(1)
                start_success = self.start_browser()
                if start_success:
                    self.driver.get(url)
                else:
                    return False
                    
            time.sleep(2)  # 페이지 로딩 대기
            return True
        except Exception as e:
            print(f"[ERROR] 사이트 열기 실패: {e}")
            return False

    def close_browser(self):
        """브라우저 종료 - 에러 처리 강화"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None  # 종료 후 드라이버 변수 초기화
                print("[INFO] 브라우저 종료됨")
                return True
            except Exception as e:
                print(f"[WARNING] 브라우저 종료 중 오류: {e}")
                self.driver = None  # 오류 시에도 참조 초기화
                return False
        return True  # 이미 닫혀 있는 경우

    def open_site(self, url):
        """버튼을 눌렀을 때만 브라우저를 실행하고 사이트 이동"""
        if not self.driver:
            print("[INFO] 브라우저가 실행되지 않아 start_browser() 호출")
            self.start_browser()

        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        print(f"[INFO] 사이트 이동: {url}")
        self.driver.get(url)
        time.sleep(2)  # 페이지 로딩 대기

    def get_page_source(self):
        """현재 페이지의 HTML 가져오기"""
        if not self.driver:
            print("[ERROR] 브라우저가 실행되지 않음")
            return None
        return self.driver.page_source  # HTML 반환

    def get_redirected_url(self):
        """현재 브라우저의 URL을 가져오는 함수"""
        if not self.driver:
            print("[ERROR] WebDriver가 실행되지 않음")
            return None
        return self.driver.current_url  # 현재 URL 반환
    
    # utils/devtools.py에 메서드 추가
    def clear_browser_cache(self):
        """브라우저 캐시 및 쿠키 삭제"""
        try:
            if self.driver:
                self.driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                self.driver.execute_cdp_cmd('Network.clearBrowserCookies', {})
                self.logger.info("브라우저 캐시 및 쿠키 삭제 완료")
                return True
            return False
        except Exception as e:
            self.logger.error(f"캐시 삭제 중 오류: {e}")
            return False