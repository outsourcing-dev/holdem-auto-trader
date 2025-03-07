# services/room_entry_service.py
import random
import time
import logging
from PyQt6.QtWidgets import QMessageBox
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class RoomEntryService:
    def __init__(self, devtools, main_window, room_manager, logger=None):
        """
        방 입장 서비스 초기화
        
        Args:
            devtools (DevToolsController): 브라우저 제어 객체
            main_window (QMainWindow): 메인 윈도우 객체
            room_manager (RoomManager): 방 관리 객체
            logger (logging.Logger, optional): 로깅을 위한 로거 객체
        """
        # 로거 설정
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # 의존성 주입
        self.devtools = devtools
        self.main_window = main_window
        self.room_manager = room_manager

    def enter_room(self):
        """
        랜덤 순서로 생성된 방 목록에서 다음 방에 입장합니다.
        방 게임 수가 10판 미만이거나 45판 이상이면 다른 방을 찾습니다.
        
        Returns:
            str: 선택된 방 이름 또는 None
        """
        try:
            # 다음에 방문할 방 가져오기
            room_name = self.room_manager.get_next_room_to_visit()
            
            if not room_name:
                QMessageBox.warning(self.main_window, "알림", "자동 매매를 시작할 방을 선택해주세요.")
                return None
            
            # 로깅
            self.logger.info(f"선택된 방: {room_name}")

            # iframe으로 전환
            self._switch_to_iframe()

            # 방 검색 및 입장
            self._search_and_enter_room(room_name)
            
            # 방 입장 후 게임 수 확인 (2초 대기 후)
            time.sleep(2)
            
            # 게임 상태 확인
            game_state = self.main_window.trading_manager.game_monitoring_service.get_current_game_state()
            if game_state:
                game_count = game_state.get('round', 0)
                self.logger.info(f"방 {room_name}의 현재 게임 수: {game_count}")
                
                # 게임 수가 10판 미만이거나 45판 이상인 경우 방 나가기
                if game_count < 10 or game_count >= 45:
                    self.logger.info(f"게임 수가 적합하지 않음 ({game_count}판). 다른 방을 찾습니다.")
                    
                    # 방 나가기
                    if self.main_window.trading_manager.game_monitoring_service.close_current_room():
                        self.logger.info("방을 성공적으로 나갔습니다.")
                        
                        # 2번 창(카지노 로비)으로 포커싱
                        window_handles = self.devtools.driver.window_handles
                        if len(window_handles) >= 2:
                            self.devtools.driver.switch_to.window(window_handles[1])
                            self.logger.info("카지노 로비 창으로 포커싱 전환")
                            
                        # 재귀적으로 다른 방 찾기
                        return self.enter_room()
                    else:
                        self.logger.error("방 나가기 실패")
                        return None
            
            return room_name

        except Exception as e:
            # 오류 로깅 및 처리
            self.logger.error(f"방 입장 중 오류 발생: {e}", exc_info=True)
            QMessageBox.warning(
                self.main_window, 
                "방 입장 실패", 
                f"선택한 방에 입장할 수 없습니다.\n오류: {str(e)}"
            )
            return None
        
    def _switch_to_iframe(self):
        """
        iframe으로 전환합니다.
        
        Raises:
            Exception: iframe 전환 중 오류 발생 시
        """
        try:
            # 기본 컨텍스트로 전환
            self.devtools.driver.switch_to.default_content()
            
            # iframe 찾기 및 전환
            iframe = self.devtools.driver.find_element(By.CSS_SELECTOR, "iframe")
            self.devtools.driver.switch_to.frame(iframe)
            
            self.logger.info("iframe으로 성공적으로 전환")
        except Exception as e:
            self.logger.error(f"iframe 전환 중 오류: {e}", exc_info=True)
            raise

    def _search_and_enter_room(self, room_name):
        """
        방을 검색하고 입장합니다.
        
        Args:
            room_name (str): 입장할 방 이름
        
        Raises:
            Exception: 방 검색 또는 입장 중 오류 발생 시
        """
        try:
            # 검색 입력 필드 찾기
            search_input = self.devtools.driver.find_element(
                By.CSS_SELECTOR, "input.TableTextInput--464ac"
            )
            search_input.clear()
            search_input.send_keys(room_name)
            self.logger.info(f"방 이름 '{room_name}' 입력 완료")

            # 검색 결과 대기 및 첫 번째 결과 클릭
            wait = WebDriverWait(self.devtools.driver, 5)
            first_result = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[data-role='search-result']")
                )
            )
            first_result.click()
            self.logger.info("첫 번째 검색 결과 클릭 완료")

            # 새 창으로 전환
            time.sleep(2)
            new_window_handles = self.devtools.driver.window_handles
            
            if len(new_window_handles) > 1:
                self.devtools.driver.switch_to.window(new_window_handles[-1])
                time.sleep(5)
                
                # UI 업데이트
                self.main_window.update_betting_status(room_name=room_name)
                self.logger.info(f"방 '{room_name}' 성공적으로 입장")

        except Exception as e:
            self.logger.error(f"방 검색 및 입장 중 오류: {e}", exc_info=True)
            raise