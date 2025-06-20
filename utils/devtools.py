import undetected_chromedriver as uc
import time
import os
import re
import subprocess
import platform
import logging

class DevToolsController:
    def __init__(self, logger=None):
        self.driver = None  # 초기에는 브라우저 실행 X
        self.logger = logger or logging.getLogger(__name__)

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
        """Chrome 브라우저 실행 - Chrome 137 최적화 버전"""
        # 이미 실행 중인 경우 먼저 닫기
        if self.driver:
            try:
                self.close_browser()
                time.sleep(1)
                print("[INFO] 기존 브라우저 종료 완료")
            except Exception as e:
                print(f"[WARNING] 기존 브라우저 종료 실패: {e}")
                self.driver = None

        # ✅ Chrome 137 호환 최적화: 단순한 설정으로 바로 시작
        try:
            print("[INFO] Chrome 137 호환 모드로 브라우저 시작...")
            
            # 가장 안전한 옵션으로 시작
            options = self._create_chrome137_compatible_options()
            
            # 버전 지정 없이 바로 시작 (호환성 문제 회피)
            self.driver = uc.Chrome(options=options)
            
            if self.driver:
                self._post_browser_setup()
                print("[INFO] Chrome 137 호환 브라우저 시작 완료")
                return True
                
        except Exception as e:
            print(f"[WARNING] Chrome 137 호환 모드 실패: {e}")
            self.driver = None
            
            # ✅ 백업: 최소한의 설정으로 재시도
            try:
                print("[INFO] 최소 설정으로 재시도...")
                options = self._create_ultra_minimal_options()
                self.driver = uc.Chrome(options=options)
                
                if self.driver:
                    self._post_browser_setup_minimal()
                    print("[INFO] 최소 설정 브라우저 시작 완료")
                    return True
                    
            except Exception as final_error:
                print(f"[ERROR] 최종 브라우저 시작 실패: {final_error}")
                self.driver = None
                return False
        
        return False

    def _create_chrome137_compatible_options(self):
        """Chrome 137 완전 호환 옵션 - 디버깅 포트 추가"""
        try:
            options = uc.ChromeOptions()
            options.headless = False
            
            # ✅ Chrome 137에서 확실히 작동하는 최소 옵션만
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            
            # ✅ 디버깅 포트 추가 (Playwright 연결용)
            options.add_argument("--remote-debugging-port=9222")
            
            print("[INFO] Chrome 137 완전 호환 옵션 설정 (디버깅 포트 포함)")
            return options
            
        except Exception as e:
            print(f"[ERROR] Chrome 137 호환 옵션 생성 실패: {e}")
            return self._create_ultra_minimal_options()

    def _create_ultra_minimal_options(self):
        """초최소 Chrome 옵션 (최후의 수단) - 디버깅 포트 추가"""
        try:
            options = uc.ChromeOptions()
            options.headless = False
            
            # ✅ 디버깅 포트는 반드시 추가
            options.add_argument("--remote-debugging-port=9222")
            
            print("[INFO] 초최소 Chrome 옵션 설정 (디버깅 포트 포함)")
            return options
            
        except Exception as e:
            print(f"[ERROR] 초최소 Chrome 옵션 생성 실패: {e}")
            # 최후의 수단에도 디버깅 포트 추가
            options = uc.ChromeOptions()
            options.add_argument("--remote-debugging-port=9222")
            return options

    def _create_stable_chrome_options(self):
        """안정적인 Chrome 옵션 (성공률 높음) - Chrome 137 호환"""
        try:
            options = uc.ChromeOptions()
            options.headless = False
            
            # ✅ Chrome 137에서 안전한 기본 설정만 사용
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-extensions")
            
            # ✅ 디버깅 포트 추가
            options.add_argument("--remote-debugging-port=9222")
            
            # ✅ 실험적 옵션 완전 제거 (Chrome 137 호환성 문제 해결)
            # options.add_experimental_option("useAutomationExtension", False)
            # options.add_experimental_option("excludeSwitches", ["enable-automation"])
            
            print("[INFO] Chrome 137 호환 안정적인 옵션 설정 완료 (디버깅 포트 포함)")
            return options
            
        except Exception as e:
            print(f"[ERROR] 안정적인 Chrome 옵션 설정 오류: {e}")
            return self._create_minimal_chrome_options()

    def _create_minimal_chrome_options(self):
        """최소한의 Chrome 옵션 (백업용)"""
        try:
            options = uc.ChromeOptions()
            options.headless = False
            options.add_argument("--disable-blink-features=AutomationControlled")
            
            # ✅ 디버깅 포트 추가
            options.add_argument("--remote-debugging-port=9222")
            
            print("[INFO] 최소한의 Chrome 옵션 설정 완료 (디버깅 포트 포함)")
            return options
            
        except Exception as e:
            print(f"[ERROR] 최소한의 Chrome 옵션 생성 오류: {e}")
            return self._create_basic_chrome_options()

    def _create_basic_chrome_options(self):
        """기본 Chrome 옵션 (최후의 수단)"""
        try:
            options = uc.ChromeOptions()
            options.headless = False
            
            # ✅ 디버깅 포트 추가
            options.add_argument("--remote-debugging-port=9222")
            
            print("[INFO] 기본 Chrome 옵션 설정 완료 (디버깅 포트 포함)")
            return options
            
        except Exception as e:
            print(f"[ERROR] 기본 Chrome 옵션 생성 실패: {e}")
            # 최후의 수단
            options = uc.ChromeOptions()
            options.add_argument("--remote-debugging-port=9222")
            return options

    def _post_browser_setup(self):
        """브라우저 시작 후 추가 설정 - Chrome 137 최적화 버전"""
        try:
            if not self.driver:
                return False
            
            # 기본 설정만 적용
            self.driver.implicitly_wait(10)
            self.driver.set_page_load_timeout(30)
            
            print("[INFO] 기본 브라우저 설정 완료")
            
            # ✅ Performance Logging 테스트 제거 (Chrome 137에서 지원 안함)
            # Performance Logging이 필요한 경우에만 별도로 테스트
            
            # CDP 설정 시도 (선택적)
            self._setup_cdp_if_available()
            
            # WebSocket 후킹 설정 (선택적)
            self._setup_websocket_hooks()
            
            return True
            
        except Exception as e:
            print(f"[WARNING] 브라우저 후처리 설정 중 오류: {e}")
            return False

    def _test_performance_logging_if_needed(self):
        """필요한 경우에만 Performance Logging 테스트"""
        try:
            logs = self.driver.get_log("performance")
            print(f"[INFO] ✅ Performance Logging 사용 가능 ({len(logs)}개 로그)")
            return True
        except Exception as e:
            print(f"[INFO] ℹ️ Performance Logging 미지원 (Chrome 137+에서 정상)")
            return False

    def _post_browser_setup_minimal(self):
        """최소한의 브라우저 설정 (백업용)"""
        try:
            if not self.driver:
                return False
            
            # 가장 기본적인 설정만
            self.driver.implicitly_wait(5)
            self.driver.set_page_load_timeout(20)
            
            print("[INFO] 최소 브라우저 설정 완료")
            return True
            
        except Exception as e:
            print(f"[WARNING] 최소 브라우저 설정 중 오류: {e}")
            return False

    def _setup_cdp_if_available(self):
        """CDP 사용 가능하면 설정"""
        try:
            # CDP 명령 테스트
            self.driver.execute_cdp_cmd('Runtime.evaluate', {'expression': '1+1'})
            
            # Network 도메인 활성화
            self.driver.execute_cdp_cmd('Network.enable', {})
            self.driver.execute_cdp_cmd('Runtime.enable', {})
            
            print("[INFO] ✅ CDP를 통한 Network 도메인 활성화 성공")
            return True
            
        except Exception as e:
            print(f"[WARNING] CDP 설정 실패 (무시하고 계속): {e}")
            return False

    def _setup_websocket_hooks(self):
        """WebSocket 연결 감지를 위한 JavaScript 후킹 설정"""
        try:
            websocket_hook_script = """
            // WebSocket 후킹을 위한 글로벌 저장소
            if (!window.websocketCapture) {
                window.websocketCapture = {
                    urls: [],
                    connections: [],
                    setupComplete: true
                };
                
                // 기존 WebSocket 생성자 백업
                window.OriginalWebSocket = window.WebSocket;
                
                // WebSocket 생성자 후킹
                window.WebSocket = function(url, protocols) {
                    console.log('🔗 WebSocket 연결 감지:', url);
                    window.websocketCapture.urls.push(url);
                    
                    const ws = new window.OriginalWebSocket(url, protocols);
                    window.websocketCapture.connections.push(ws);
                    
                    // 이벤트 리스너 추가
                    ws.addEventListener('open', function() {
                        console.log('📡 WebSocket 연결 열림:', url);
                    });
                    
                    return ws;
                };
                
                console.log('WebSocket 후킹 설정 완료');
            }
            
            return window.websocketCapture.setupComplete ? 'WebSocket 후킹 활성화됨' : 'WebSocket 후킹 실패';
            """
            
            result = self.driver.execute_script(websocket_hook_script)
            print(f"[INFO] WebSocket 후킹 설정: {result}")
            return True
            
        except Exception as e:
            print(f"[WARNING] WebSocket 후킹 설정 실패: {e}")
            return False

    def open_site(self, url):
        """사이트 열기 - 최적화된 버전"""
        try:
            # 브라우저가 없으면 시작
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
                print(f"[INFO] 사이트 로드 완료: {url}")
            except Exception as e:
                print(f"[ERROR] 페이지 이동 중 오류 발생: {e}")
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
    
    def clear_browser_cache(self):
        """브라우저 캐시 및 쿠키 삭제"""
        try:
            if self.driver:
                self.driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                self.driver.execute_cdp_cmd('Network.clearBrowserCookies', {})
                print("[INFO] 브라우저 캐시 및 쿠키 삭제 완료")
                return True
            return False
        except Exception as e:
            print(f"[ERROR] 캐시 삭제 중 오류: {e}")
            return False

    # ✅ Performance Logging 관련 메서드들 (안전한 버전)
    def get_performance_logs(self):
        """Performance 로그 안전하게 가져오기 - Chrome 137 호환"""
        try:
            if not self.driver:
                return []
            
            # Chrome 137+에서는 performance 로그가 지원되지 않을 수 있음
            return self.driver.get_log("performance")
            
        except Exception as e:
            # Chrome 137+에서는 정상적인 동작이므로 경고 레벨 낮춤
            # print(f"[WARNING] Performance 로그 가져오기 실패: {e}")
            return []

    def get_browser_logs(self):
        """Browser 콘솔 로그 안전하게 가져오기"""
        try:
            if not self.driver:
                return []
            
            return self.driver.get_log("browser")
            
        except Exception as e:
            print(f"[WARNING] Browser 로그 가져오기 실패: {e}")
            return []

    def get_captured_websockets(self):
        """JavaScript 후킹으로 캡처된 웹소켓 URL들 가져오기"""
        try:
            if not self.driver:
                return []
            
            urls = self.driver.execute_script("""
                return window.websocketCapture ? 
                    window.websocketCapture.urls || [] : 
                    [];
            """)
            return urls or []
            
        except Exception as e:
            print(f"[WARNING] 캡처된 웹소켓 URL 가져오기 실패: {e}")
            return []

    def execute_javascript(self, script):
        """JavaScript 실행"""
        try:
            if not self.driver:
                return None
            return self.driver.execute_script(script)
        except Exception as e:
            print(f"[WARNING] JavaScript 실행 실패: {e}")
            return None

    def refresh_page(self):
        """페이지 새로고침"""
        try:
            if not self.driver:
                return False
            self.driver.refresh()
            return True
        except Exception as e:
            print(f"[WARNING] 페이지 새로고침 실패: {e}")
            return False

    def is_driver_alive(self):
        """드라이버가 살아있는지 확인"""
        try:
            if not self.driver:
                return False
            
            # 간단한 명령으로 연결 상태 확인
            self.driver.current_url
            return True
            
        except Exception:
            return False