# services/betting_service.py
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class BettingService:
    def __init__(self, devtools, main_window, logger=None):
        """
        베팅 서비스 초기화
        
        Args:
            devtools (DevToolsController): 브라우저 제어 객체
            main_window (QMainWindow): 메인 윈도우 객체
            logger (logging.Logger, optional): 로깅을 위한 로거 객체
        """
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        self.devtools = devtools
        self.main_window = main_window
        self.has_bet_current_round = False

    def place_bet(self, bet_type, current_room_name, game_count, is_trading_active):
        """
        베팅 타입(P 또는 B)에 따라 적절한 베팅 영역을 클릭합니다.
        중복 클릭 방지를 위해 베팅 상태를 기록합니다.
        
        Args:
            bet_type (str): 'P'(플레이어) 또는 'B'(뱅커)
            current_room_name (str): 현재 방 이름
            game_count (int): 현재 게임 카운트
            is_trading_active (bool): 자동 매매 활성화 상태
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 자동 매매 활성화 상태 확인
            if not is_trading_active:
                self.logger.info("자동 매매가 활성화되지 않았습니다.")
                return False
            
            # 이미 베팅했는지 확인 (중복 베팅 방지)
            if self.has_bet_current_round:
                self.logger.info("이미 현재 라운드에 베팅했습니다.")
                return False
            
            # iframe으로 전환
            self.devtools.driver.switch_to.default_content()
            iframe = self.devtools.driver.find_element(By.CSS_SELECTOR, "iframe")
            self.devtools.driver.switch_to.frame(iframe)
            
            # 베팅 대상 선택
            if bet_type == 'P':
                # Player 영역 찾기 및 클릭
                selector = "div.spot--5ad7f[data-betspot-destination='Player']"
                self.logger.info(f"Player 베팅 영역 클릭 시도: {selector}")
            elif bet_type == 'B':
                # Banker 영역 찾기 및 클릭
                selector = "div.spot--5ad7f[data-betspot-destination='Banker']"
                self.logger.info(f"Banker 베팅 영역 클릭 시도: {selector}")
            else:
                self.logger.error(f"잘못된 베팅 타입: {bet_type}")
                return False
            
            # 요소 찾기
            bet_element = WebDriverWait(self.devtools.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            
            # 요소가 활성화되어 있는지 확인
            is_active = 'active--dc7b3' in bet_element.get_attribute('class')
            if is_active:
                self.logger.info(f"이미 {bet_type} 영역이 활성화되어 있습니다.")
            else:
                # 클릭
                bet_element.click()
                self.logger.info(f"{bet_type} 영역 클릭 완료!")
            
            # 베팅 상태 기록 (중복 베팅 방지)
            self.has_bet_current_round = True
            
            # UI 업데이트
            self.main_window.update_betting_status(
                room_name=f"{current_room_name} (게임 수: {game_count}, 베팅: {bet_type})"
            )
            
            return True
        
        except Exception as e:
            # 오류 로깅
            self.logger.error(f"베팅 중 오류 발생: {e}", exc_info=True)
            return False
    
    def reset_betting_state(self):
        """베팅 상태 초기화"""
        self.has_bet_current_round = False
        self.logger.info("베팅 상태 초기화 완료")
        
    def check_betting_result(self, column, latest_result, current_room_name, result_count):
        """
        특정 열의 베팅 결과를 확인하고 UI를 업데이트합니다.
        
        Args:
            column (str): 확인할 열 문자 (예: 'B', 'C', 'D')
            latest_result (str): 최신 게임 결과 ('P', 'B', 'T')
            current_room_name (str): 현재 방 이름
            result_count (int): 결과 카운트
            
        Returns:
            tuple: (is_win, result_count)
        """
        try:
            from utils.excel_manager import ExcelManager
            excel_manager = ExcelManager()
            
            # 현재 PICK 값 확인 (현재 열의 12행)
            _, current_pick = excel_manager.check_betting_needed(column)
            
            # 결과 확인 (현재 열의 16행)
            is_win, result_value = excel_manager.check_result(column)
            
            # 결과 번호 증가
            result_count += 1
            
            # UI에 결과 추가
            result_text = "적중" if is_win else "실패"
            self.main_window.add_betting_result(
                no=result_count,
                room_name=current_room_name,
                step=1,  # 현재는 단계 구현 없음, 향후 마틴 단계 추가 필요
                result=result_text
            )
            
            marker = "O" if is_win else "X"
            self.main_window.update_betting_status(
                step_markers={1: marker}  # 현재는 첫 번째 단계만 표시
            )
            
            self.logger.info(f"베팅 결과 확인 - 열: {column}, PICK: {current_pick}, 결과: {latest_result}, 승패: {result_text}")
            
            return is_win, result_count
            
        except Exception as e:
            # 오류 로깅
            self.logger.error(f"베팅 결과 확인 중 오류 발생: {e}", exc_info=True)
            return False, result_count