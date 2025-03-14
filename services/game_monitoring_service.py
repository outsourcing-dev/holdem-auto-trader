# services/game_monitoring_service.py
import logging
from selenium.webdriver.common.by import By
from modules.game_detector import GameDetector
import time
from utils.iframe_utils import IframeManager, switch_to_iframe_with_retry  # 추가: iframe 유틸리티 임포트

class GameMonitoringService:
    def __init__(self, devtools, main_window, logger=None):
        """
        게임 모니터링 서비스 초기화
        
        Args:
            devtools (DevToolsController): 브라우저 제어 객체
            main_window (QMainWindow): 메인 윈도우 객체
            logger (logging.Logger, optional): 로깅을 위한 로거 객체
        """
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        self.devtools = devtools
        self.main_window = main_window
        self.game_detector = GameDetector()
        
        # 추가: iframe 매니저 초기화
        self.iframe_manager = None

    def get_current_game_state(self, log_always=True):
        """
        현재 게임 상태를 분석합니다.
        
        Args:
            log_always (bool): 항상 로그를 남길지 여부
        
        Returns:
            dict: 게임 상태 정보
        """
        try:
            if log_always:
                self.logger.info("현재 게임 상태 분석 중...")
            
            # 추가: iframe 매니저 초기화
            self.iframe_manager = IframeManager(self.devtools.driver)
            
            # 기본 프레임으로 전환
            self.devtools.driver.switch_to.default_content()
            
            # 방법 1: 기존 방식으로 iframe 전환 시도
            iframe_switched = False
            try:
                iframe = self.devtools.driver.find_element(By.CSS_SELECTOR, "iframe")
                self.devtools.driver.switch_to.frame(iframe)
                iframe_switched = True
                
                # 중첩된 iframe 확인
                nested_iframes = self.devtools.driver.find_elements(By.TAG_NAME, "iframe")
                if nested_iframes:
                    self.logger.info("중첩된 iframe이 발견되어 전환 시도")
                    self.devtools.driver.switch_to.frame(nested_iframes[0])
            except Exception as e:
                self.logger.warning(f"기본 iframe 전환 실패: {e}")
                self.devtools.driver.switch_to.default_content()
            
            # 방법 2: 실패 시 유틸리티 함수 사용
            if not iframe_switched:
                self.logger.info("자동 iframe 전환 시도")
                iframe_switched = switch_to_iframe_with_retry(self.devtools.driver)
                
                if not iframe_switched:
                    self.logger.error("모든 iframe 전환 방법 실패")
                    return None
            
            # 페이지 소스 가져오기
            html_content = self.devtools.driver.page_source
            
            # 게임 상태 감지
            game_state = self.game_detector.detect_game_state(html_content)
            
            return game_state
            
        except Exception as e:
            # 오류 로깅
            self.logger.error(f"게임 상태 분석 중 오류 발생: {e}", exc_info=True)
            
            # 오류 발생 시 기본 프레임으로 복귀 시도
            try:
                self.devtools.driver.switch_to.default_content()
            except:
                pass
                
            return None

    def close_current_room(self):
        """현재 열린 방을 종료하고 카지노 로비 창으로 포커싱 전환"""
        try:
            # 방 나가기 전 최종 잔액 업데이트 - 실패해도 계속 진행
            try:
                balance = self.main_window.trading_manager.balance_service.update_balance_after_bet_result()
                self.logger.info(f"방 나가기 전 최종 잔액: {balance:,}원")
            except Exception as e:
                self.logger.warning(f"방 나가기 전 잔액 확인 실패: {e}")
                # 실패해도 계속 진행
            
            # 현재 창이 몇 개인지 확인
            window_handles = self.devtools.driver.window_handles
            self.logger.info(f"현재 열린 창 개수: {len(window_handles)}")
            
            # 추가: iframe 매니저 초기화
            self.iframe_manager = IframeManager(self.devtools.driver)
            
            # iframe 내부로 이동하여 종료 버튼 찾기
            try:
                # 기본 프레임으로 전환
                self.devtools.driver.switch_to.default_content()
                
                # 방법 1: 기존 방식으로 iframe 전환 시도
                iframe_switched = False
                try:
                    iframe = self.devtools.driver.find_element(By.CSS_SELECTOR, "iframe")
                    self.devtools.driver.switch_to.frame(iframe)
                    iframe_switched = True
                    
                    # 중첩된 iframe 확인
                    nested_iframes = self.devtools.driver.find_elements(By.TAG_NAME, "iframe")
                    if nested_iframes:
                        self.logger.info("종료 버튼 찾기: 중첩된 iframe이 발견되어 전환")
                        self.devtools.driver.switch_to.frame(nested_iframes[0])
                except Exception as e:
                    self.logger.warning(f"종료 버튼 찾기: iframe 전환 실패: {e}")
                    self.devtools.driver.switch_to.default_content()
                
                # 방법 2: 실패 시 유틸리티 함수 사용
                if not iframe_switched:
                    self.logger.info("종료 버튼 찾기: 자동 iframe 전환 시도")
                    iframe_switched = switch_to_iframe_with_retry(self.devtools.driver)
                
                self.logger.info("iframe 내부에서 종료 버튼 탐색 중...")

                # 정확한 종료 버튼 선택자 사용
                try:
                    # 기존 코드와 동일하게 WebDriverWait 사용
                    from selenium.webdriver.support.ui import WebDriverWait
                    from selenium.webdriver.support import expected_conditions as EC
                    
                    close_button = WebDriverWait(self.devtools.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-role='close-button']"))
                    )
                    close_button.click()
                    self.logger.info("방 종료 버튼 클릭 완료!")
                    # 클릭 후 약간의 대기시간 추가
                    time.sleep(1)
                except Exception as e:
                    self.logger.warning(f"종료 버튼 클릭 실패: {e}")
                    # 실패해도 계속 진행
            except Exception as e:
                self.logger.warning(f"iframe 전환 또는 종료 버튼 찾기 실패: {e}")
                # 실패해도 계속 진행
            
            # 메인 프레임으로 전환 시도
            try:
                self.devtools.driver.switch_to.default_content()
            except:
                self.logger.warning("메인 프레임 전환 실패")
            
            # 현재 창의 상태 다시 확인
            try:
                current_url = self.devtools.driver.current_url
                self.logger.info(f"현재 URL: {current_url}")
                
                # URL로 이미 로비에 있는지 확인
                if "game" not in current_url.lower() and "live" not in current_url.lower():
                    self.logger.info("이미 로비 또는 다른 페이지에 있는 것으로 감지됨")
                
                # 현재 창이 몇 개인지 다시 확인
                window_handles = self.devtools.driver.window_handles
                
                # 로비 창으로 전환 (일반적으로 두 번째 창)
                if len(window_handles) >= 2:
                    self.devtools.driver.switch_to.window(window_handles[1])
                    self.logger.info("카지노 로비 창으로 포커싱 전환 완료")
                    return True
                elif len(window_handles) == 1:
                    # 창이 하나만 있으면 그 창을 사용
                    self.devtools.driver.switch_to.window(window_handles[0])
                    self.logger.info("단일 창으로 포커싱 전환")
                    return True
                else:
                    self.logger.warning("열린 창이 없습니다.")
                    return False
            except Exception as e:
                self.logger.error(f"창 전환 실패: {e}")
                return False

        except Exception as e:
            self.logger.error(f"방 종료 시도 중 전체 오류: {e}", exc_info=True)
            
            # 오류 발생 시에도 최대한 로비 창으로 복귀 시도
            try:
                self.devtools.driver.switch_to.default_content()
                window_handles = self.devtools.driver.window_handles
                if len(window_handles) >= 2:
                    self.devtools.driver.switch_to.window(window_handles[1])
                    self.logger.info("오류 후 복구: 카지노 로비 창으로 포커싱 전환")
                    return True
                elif len(window_handles) == 1:
                    self.devtools.driver.switch_to.window(window_handles[0])
                    self.logger.info("오류 후 복구: 단일 창으로 포커싱 전환")
                    return True
            except:
                pass
                
            return False