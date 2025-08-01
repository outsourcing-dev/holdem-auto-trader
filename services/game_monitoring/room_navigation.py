"""
방 네비게이션 전용 모듈
game_monitoring_service.py에서 분리된 방 이동 관련 로직
"""
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.common_iframe import IframeNavigator


class RoomNavigationManager:
    """방 네비게이션 전담 클래스"""
    
    def __init__(self, devtools, logger=None):
        self.devtools = devtools
        self.logger = logger or logging.getLogger(__name__)
        
        # iframe 네비게이터 안전한 초기화
        try:
            if devtools and devtools.driver:
                self.iframe_navigator = IframeNavigator(devtools.driver, self.logger)
            else:
                self.logger.warning("RoomNavigationManager: driver가 None - iframe 네비게이터 없이 초기화")
                self.iframe_navigator = None
        except Exception as e:
            self.logger.error(f"RoomNavigationManager iframe 네비게이터 초기화 실패: {e}")
            self.iframe_navigator = None
    
    def try_close_room(self):
        """방 종료 시도 - 확장된 패턴"""
        try:
            # 다양한 종료 버튼 selector 시도 (우선순위 순)
            close_selectors = [
                # 명확한 종료/닫기 버튼
                "button[onclick*='close']",
                "button[onclick*='exit']",
                "button[onclick*='leave']",
                "button[onclick*='quit']",
                
                # 클래스 기반
                ".close-btn", ".close-button",
                ".exit-btn", ".exit-button", 
                ".leave-btn", ".leave-button",
                ".quit-btn", ".quit-button",
                
                # 일반적인 패턴
                "[class*='close']",
                "[class*='exit']",
                "[class*='leave']",
                "[class*='quit']",
                
                # 한국어 패턴
                "button:contains('나가기')",
                "button:contains('종료')",
                "button:contains('닫기')",
                "a:contains('나가기')",
                "a:contains('종료')",
                
                # 일반적인 버튼 (텍스트 기반)
                "//button[contains(text(), '나가기')]",
                "//button[contains(text(), '종료')]",
                "//button[contains(text(), '닫기')]",
                "//button[contains(text(), 'EXIT')]",
                "//button[contains(text(), 'CLOSE')]",
                "//a[contains(text(), '나가기')]",
                "//a[contains(text(), '종료')]",
                
                # 이미지 버튼
                "img[alt*='close']",
                "img[alt*='exit']",
                "img[src*='close']",
                "img[src*='exit']"
            ]
            
            for selector in close_selectors:
                try:
                    # XPath 패턴인지 확인
                    if selector.startswith('//'):
                        close_button = self.iframe_navigator.wait_for_clickable(
                            By.XPATH, selector, timeout=1
                        )
                    else:
                        close_button = self.iframe_navigator.wait_for_clickable(
                            By.CSS_SELECTOR, selector, timeout=1
                        )
                    
                    if close_button:
                        close_button.click()
                        self.logger.info(f"방 종료 버튼 클릭 성공: {selector}")
                        return True
                        
                except Exception as e:
                    # 개별 selector 실패는 무시하고 다음으로
                    self.logger.debug(f"selector '{selector}' 실패: {e}")
                    continue
            
            self.logger.warning("모든 종료 버튼 패턴에서 버튼을 찾을 수 없음")
            return False
            
        except Exception as e:
            self.logger.error(f"방 종료 시도 중 전체 오류: {e}")
            return False
    
    def switch_to_lobby_window(self):
        """로비 창으로 전환"""
        try:
            windows = self.devtools.driver.window_handles
            
            for window in windows:
                self.devtools.driver.switch_to.window(window)
                current_url = self.devtools.driver.current_url
                
                # 로비 URL 패턴 확인
                if any(pattern in current_url.lower() for pattern in ['lobby', 'main', 'index']):
                    self.logger.info(f"로비 창으로 전환: {current_url}")
                    return True
            
            # 첫 번째 창으로 전환 (fallback)
            if windows:
                self.devtools.driver.switch_to.window(windows[0])
                self.logger.info("첫 번째 창으로 전환")
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"로비 창 전환 중 오류: {e}")
            return False
    
    def handle_room_exit_sequence(self):
        """방 나가기 전체 시퀀스 처리"""
        try:
            self.logger.info("방 나가기 시퀀스 시작")
            
            # 1. iframe 전환
            if not self.iframe_navigator.switch_to_game_iframe():
                self.logger.warning("게임 iframe 전환 실패")
                return False
            
            # 2. 방 닫기 시도
            if self.try_close_room():
                self.logger.info("방 종료 버튼 클릭 완료")
                
                # 3. 종료 대기
                WebDriverWait(self.devtools.driver, 2).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            else:
                self.logger.warning("방 종료 버튼을 찾을 수 없음")
            
            # 4. 로비 창으로 전환
            if self.switch_to_lobby_window():
                self.logger.info("로비 창 전환 완료")
                return True
            else:
                self.logger.warning("로비 창 전환 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"방 나가기 시퀀스 중 오류: {e}")
            return False
    
    def wait_for_room_load(self, timeout=10):
        """방 로딩 완료 대기"""
        try:
            # 게임 요소들이 로드될 때까지 대기
            game_indicators = [
                ".game-table",
                ".betting-area", 
                "[class*='game']",
                "[class*='table']"
            ]
            
            for indicator in game_indicators:
                element = self.iframe_navigator.wait_for_element(
                    By.CSS_SELECTOR, indicator, timeout=timeout//len(game_indicators)
                )
                if element:
                    self.logger.info(f"방 로딩 완료 확인: {indicator}")
                    return True
            
            # fallback: 페이지 로딩 상태 확인
            WebDriverWait(self.devtools.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"방 로딩 대기 중 오류: {e}")
            return False