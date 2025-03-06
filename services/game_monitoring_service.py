# services/game_monitoring_service.py
import logging
from selenium.webdriver.common.by import By
from modules.game_detector import GameDetector

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
        
    def get_current_game_state(self):
        """
        현재 게임 상태를 분석합니다.
        
        Returns:
            dict: 게임 상태 정보
        """
        try:
            self.logger.info("현재 게임 상태 분석 중...")
            
            # iframe으로 전환
            self.devtools.driver.switch_to.default_content()
            iframe = self.devtools.driver.find_element(By.CSS_SELECTOR, "iframe")
            self.devtools.driver.switch_to.frame(iframe)
            
            # 페이지 소스 가져오기
            html_content = self.devtools.driver.page_source
            
            # 게임 상태 감지
            game_state = self.game_detector.detect_game_state(html_content)
            
            return game_state
            
        except Exception as e:
            # 오류 로깅
            self.logger.error(f"게임 상태 분석 중 오류 발생: {e}", exc_info=True)
            return None
            
    def close_current_room(self):
        """현재 열린 방을 종료"""
        try:
            # iframe 내부로 이동하여 종료 버튼 찾기
            self.devtools.driver.switch_to.default_content()
            iframe = self.devtools.driver.find_element(By.CSS_SELECTOR, "iframe")
            self.devtools.driver.switch_to.frame(iframe)
            self.logger.info("iframe 내부에서 종료 버튼 탐색 중...")

            # 종료 버튼 찾기 및 클릭
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            close_button = WebDriverWait(self.devtools.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-role='close-button']"))
            )
            close_button.click()
            self.logger.info("방 종료 버튼 클릭 완료!")

            # 다시 메인 프레임으로 전환
            self.devtools.driver.switch_to.default_content()
            return True

        except Exception as e:
            # 오류 로깅
            self.logger.error(f"방 종료 실패: {e}", exc_info=True)
            return False