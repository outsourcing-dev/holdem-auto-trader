import time
import logging
import psutil
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from selenium.common.exceptions import WebDriverException, TimeoutException

class DevToolsController:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        self.driver = None
        self.service = None
        self.debug_port = None
        
        # Chrome 시작 재시도 설정
        self.max_start_retries = 3
        self.retry_delay = 2
        
    def start_browser(self):
        """
        간소화된 Chrome 브라우저 시작 (Basic 모드만 사용)
        """
        try:
            # 기존 Chrome 프로세스 정리
            self._cleanup_chrome_processes()
            
            # Basic 모드로 여러 번 시도
            for attempt in range(self.max_start_retries):
                try:
                    self.logger.info(f"Chrome 브라우저 시작 시도 {attempt + 1}/{self.max_start_retries}")
                    
                    if self._start_chrome_basic():
                        self.logger.info("✅ Chrome 브라우저 시작 성공")
                        return True
                        
                except Exception as e:
                    self.logger.warning(f"시도 {attempt + 1} 실패: {e}")
                    
                    # 실패한 경우 정리 후 재시도
                    if self.driver:
                        try:
                            self.driver.quit()
                        except:
                            pass
                        self.driver = None
                    
                    if attempt < self.max_start_retries - 1:
                        self.logger.info(f"{self.retry_delay}초 후 재시도...")
                        time.sleep(self.retry_delay)
                        self._cleanup_chrome_processes()
            
            self.logger.error("모든 Chrome 시작 시도 실패")
            return False
            
        except Exception as e:
            self.logger.error(f"Chrome 브라우저 시작 중 치명적 오류: {e}")
            return False

    def _cleanup_chrome_processes(self):
        """기존 Chrome 프로세스 정리"""
        try:
            self.logger.info("기존 Chrome 프로세스 정리 중...")
            
            chrome_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_info = proc.info
                    if proc_info['name'] and 'chrome' in proc_info['name'].lower():
                        cmdline = ' '.join(proc_info['cmdline'] or [])
                        # 자동화 관련 Chrome만 종료 (일반 사용자 Chrome은 보호)
                        if any(keyword in cmdline.lower() for keyword in [
                            'remote-debugging', 'disable-blink-features', 'test-type'
                        ]):
                            chrome_processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Chrome 프로세스 종료
            for proc in chrome_processes:
                try:
                    proc.terminate()
                    self.logger.debug(f"Chrome 프로세스 종료: PID {proc.pid}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # 종료 대기
            if chrome_processes:
                time.sleep(2)
                
                # 강제 종료
                for proc in chrome_processes:
                    try:
                        if proc.is_running():
                            proc.kill()
                            self.logger.debug(f"Chrome 프로세스 강제 종료: PID {proc.pid}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                        
                self.logger.info(f"기존 Chrome 프로세스 {len(chrome_processes)}개 정리 완료")
            
        except Exception as e:
            self.logger.warning(f"Chrome 프로세스 정리 중 오류: {e}")

    def _start_chrome_basic(self):
        """검증된 Basic 모드로 Chrome 시작"""
        try:
            self.logger.info("🔄 Chrome 시작 중...")
            
            # ChromeOptions를 매번 새로 생성 (재사용 방지)
            options = uc.ChromeOptions()
            
            # 검증된 기본 옵션만 사용
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            # 임시 사용자 데이터 디렉토리 생성
            user_data_dir = self._get_temp_user_data_dir()
            if user_data_dir:
                options.add_argument(f'--user-data-dir={user_data_dir}')
            
            # Chrome 138 버전 명시적 지정 (현재 환경)
            self.logger.info("Chrome 138 버전 드라이버로 시작")
            self.driver = uc.Chrome(options=options, version_main=138)
            
            # 연결 테스트
            self.driver.get("about:blank")
            time.sleep(1)
            
            self.logger.info("✅ Chrome 시작 성공")
            return True
            
        except Exception as e:
            self.logger.warning(f"Chrome 시작 실패: {e}")
            return False

    def _get_temp_user_data_dir(self):
        """임시 사용자 데이터 디렉토리 생성"""
        try:
            import tempfile
            import uuid
            
            temp_dir = tempfile.gettempdir()
            unique_id = str(uuid.uuid4())[:8]
            user_data_dir = os.path.join(temp_dir, f"chrome_auto_{unique_id}")
            
            os.makedirs(user_data_dir, exist_ok=True)
            return user_data_dir
            
        except Exception as e:
            self.logger.warning(f"임시 디렉토리 생성 실패: {e}")
            return ""

    def close_browser(self):
        """브라우저 안전하게 종료"""
        try:
            if self.driver:
                self.logger.info("브라우저 종료 중...")
                
                try:
                    # 모든 창 닫기
                    self.driver.quit()
                except Exception as e:
                    self.logger.warning(f"브라우저 정상 종료 실패: {e}")
                    
                finally:
                    self.driver = None
                    
                # 잔여 프로세스 정리
                time.sleep(1)
                self._cleanup_chrome_processes()
                
                self.logger.info("브라우저 종료 완료")
                
        except Exception as e:
            self.logger.error(f"브라우저 종료 중 오류: {e}")

    def get_performance_logs(self):
        """Performance 로그 가져오기"""
        try:
            if not self.driver:
                return []
            
            logs = []
            try:
                # 기본 방식 시도
                logs = self.driver.get_log('performance')
            except Exception:
                # 실패 시 CDP 방식으로 대체
                try:
                    result = self.driver.execute_cdp_cmd('Log.enable', {})
                    entries = self.driver.execute_cdp_cmd('Log.getEntries', {})
                    logs = entries.get('entries', [])
                except Exception as e:
                    self.logger.debug(f"CDP 로그 수집 실패: {e}")
                    logs = []
            
            return logs
            
        except Exception as e:
            self.logger.debug(f"Performance 로그 가져오기 실패: {e}")
            return []

    def is_browser_active(self):
        """브라우저가 활성 상태인지 확인"""
        try:
            if not self.driver:
                return False
            
            # 간단한 명령으로 브라우저 응답 확인
            self.driver.current_url
            return True
            
        except Exception:
            return False

    def refresh_browser(self):
        """브라우저 새로고침"""
        try:
            if self.driver:
                self.driver.refresh()
                time.sleep(2)
                return True
            return False
            
        except Exception as e:
            self.logger.warning(f"브라우저 새로고침 실패: {e}")
            return False

    def get_browser_info(self):
        """브라우저 정보 반환"""
        try:
            if not self.driver:
                return {"status": "inactive"}
            
            return {
                "status": "active",
                "current_url": self.driver.current_url,
                "title": self.driver.title,
                "window_handles": len(self.driver.window_handles),
                "capabilities": {
                    "browser_name": self.driver.capabilities.get('browserName'),
                    "browser_version": self.driver.capabilities.get('browserVersion'),
                    "platform": self.driver.capabilities.get('platformName')
                }
            }
            
        except Exception as e:
            self.logger.warning(f"브라우저 정보 수집 실패: {e}")
            return {"status": "error", "error": str(e)}

    def wait_for_element(self, by, value, timeout=10):
        """요소 대기"""
        try:
            if not self.driver:
                return None
            
            wait = WebDriverWait(self.driver, timeout)
            element = wait.until(EC.presence_of_element_located((by, value)))
            return element
            
        except TimeoutException:
            self.logger.warning(f"요소 대기 시간 초과: {by}={value}")
            return None
        except Exception as e:
            self.logger.warning(f"요소 대기 실패: {e}")
            return None

    def safe_navigate(self, url):
        """안전한 페이지 이동"""
        try:
            if not self.driver:
                self.logger.error("브라우저가 시작되지 않았습니다.")
                return False
            
            self.logger.info(f"페이지 이동: {url}")
            self.driver.get(url)
            
            # 페이지 로드 대기
            WebDriverWait(self.driver, 30).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            time.sleep(2)  # 추가 안정화 대기
            return True
            
        except TimeoutException:
            self.logger.warning("페이지 로드 시간 초과")
            return False
        except Exception as e:
            self.logger.error(f"페이지 이동 실패: {e}")
            return False

    def execute_safe_script(self, script):
        """안전한 JavaScript 실행"""
        try:
            if not self.driver:
                return None
            
            return self.driver.execute_script(script)
            
        except Exception as e:
            self.logger.warning(f"JavaScript 실행 실패: {e}")
            return None

    def get_debug_info(self):
        """디버그 정보 반환"""
        try:
            info = {
                "driver_active": self.driver is not None,
                "browser_responsive": self.is_browser_active(),
                "debug_port": self.debug_port,
                "chrome_processes": []
            }
            
            # Chrome 프로세스 정보
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'chrome' in proc.info['name'].lower():
                        info["chrome_processes"].append({
                            "pid": proc.info['pid'],
                            "name": proc.info['name'],
                            "cmdline": ' '.join(proc.info['cmdline'] or [])[:100]
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return info
            
        except Exception as e:
            self.logger.error(f"디버그 정보 수집 실패: {e}")
            return {"error": str(e)}

    def emergency_restart(self):
        """비상 재시작"""
        try:
            self.logger.warning("브라우저 비상 재시작 실행")
            
            # 강제 종료
            self.close_browser()
            time.sleep(3)
            
            # 재시작 - 무한 루프 방지를 위해 False 반환
            self.logger.info("비상 재시작 완료 - 다음 작업 시 브라우저가 자동으로 시작됩니다")
            return False  # start_browser 호출 제거로 무한 루프 방지
            
        except Exception as e:
            self.logger.error(f"비상 재시작 실패: {e}")
            return False

    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            self.close_browser()
        except:
            pass