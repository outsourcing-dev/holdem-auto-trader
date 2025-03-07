# services/betting_service.py
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

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
        self.current_bet_round = 0  # 현재 베팅한 라운드 번호
        self.last_bet_type = None   # 마지막으로 베팅한 타입

    # services/betting_service.py
    def place_bet(self, bet_type, current_room_name, game_count, is_trading_active, bet_amount=None):
        """
        베팅 타입(P 또는 B)에 따라 적절한 베팅 영역을 클릭합니다.
        중복 클릭 방지를 위해 베팅 상태를 기록합니다.
        
        Args:
            bet_type (str): 'P'(플레이어) 또는 'B'(뱅커)
            current_room_name (str): 현재 방 이름
            game_count (int): 현재 게임 카운트
            is_trading_active (bool): 자동 매매 활성화 상태
            bet_amount (int, optional): 배팅 금액 (None이면 마틴 단계에서 가져옴)
        
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
            
            # 현재 게임 상태 확인 - 배팅 가능한지 체크
            try:
                # 게임 상태 표시 요소 확인
                game_status_element = self.devtools.driver.find_element(By.CSS_SELECTOR, "div[data-role='game-status']")
                game_status_text = game_status_element.text if game_status_element else ""
                
                # 배팅 불가능 상태인지 확인
                betting_disabled = False
                
                if "PLEASE WAIT" in game_status_text.upper() or "NO MORE BETS" in game_status_text.upper():
                    self.logger.info(f"현재 게임 상태가 배팅 불가능 상태입니다: {game_status_text}")
                    betting_disabled = True
                
                # 칩 클릭 가능 상태 확인 (첫 번째 칩 요소로 테스트)
                try:
                    chip_element = self.devtools.driver.find_element(By.CSS_SELECTOR, "div.chip--29b81[data-role='chip']")
                    chip_class = chip_element.get_attribute("class")
                    if "disabled" in chip_class or not chip_element.is_enabled():
                        self.logger.info("칩 요소가 비활성화되어 있습니다. 배팅이 불가능합니다.")
                        betting_disabled = True
                except Exception as e:
                    self.logger.warning(f"칩 상태 확인 중 오류: {e}")
                    # 칩 상태 확인 실패는 배팅 금지 조건으로 처리하지 않음
                
                if betting_disabled:
                    self.logger.info("현재 배팅이 불가능한 상태입니다. 다음 게임을 기다립니다.")
                    return False
                    
            except Exception as e:
                pass
                # self.logger.warning(f"게임 상태 확인 중 오류: {e}")
                # 게임 상태 확인에 실패하더라도 계속 진행 (추후 칩 클릭 시 에러 처리)
            
            # 베팅 전 현재 총 베팅 금액 확인
            try:
                total_bet_element = self.devtools.driver.find_element(By.CSS_SELECTOR, "span[data-role='total-bet-label-value']")
                before_bet_amount_text = total_bet_element.text
                self.logger.info(f"베팅 전 총 베팅 금액: {before_bet_amount_text}")
                
                # 숫자만 추출 (₩과 콤마, 특수 문자 제거)
                before_bet_amount = int(before_bet_amount_text.replace('₩', '').replace(',', '').replace('⁩', '').replace('⁦', '').strip() or '0')
                
                # "지난 우승" 표시 확인
                last_win_element = self.devtools.driver.find_element(By.CSS_SELECTOR, "span[data-role='total-bet-label-title']")
                is_last_win = "지난 우승" in last_win_element.text if last_win_element else False
                
                # 새 라운드 시작 시 배팅 금액이 0이 아니면서 "지난 우승"이 아닌 경우에만 경고 로그
                if before_bet_amount != 0 and not is_last_win:
                    self.logger.warning(f"새 라운드인데 배팅 금액이 0이 아닙니다: {before_bet_amount}원")
                elif is_last_win:
                    self.logger.info(f"지난 우승 금액 감지: {before_bet_amount}원")
            except Exception as e:
                self.logger.warning(f"베팅 전 총 베팅 금액 확인 실패: {e}")
                before_bet_amount = 0
            # 베팅 금액이 지정되지 않은 경우 마틴 서비스에서 가져오기
            if bet_amount is None:
                # 마틴 서비스에서 현재 베팅 금액 가져오기
                bet_amount = self.main_window.trading_manager.martin_service.get_current_bet_amount()
            
            self.logger.info(f"현재 베팅 금액: {bet_amount:,}원")
            
            # 사용 가능한 칩 금액 (큰 단위부터 처리)
            available_chips = [100000, 25000, 5000, 2000, 1000]
            
            # 각 칩별로 필요한 클릭 횟수 계산
            chip_clicks = {}
            remaining_amount = bet_amount
            
            for chip in available_chips:
                clicks = remaining_amount // chip
                if clicks > 0:
                    chip_clicks[chip] = clicks
                    remaining_amount %= chip
            
            self.logger.info(f"베팅 금액 {bet_amount:,}원 -> 칩별 클릭 횟수: {chip_clicks}")
            
            # 계산된 칩별로 클릭 수행
            total_clicks = sum(chip_clicks.values())
            if total_clicks == 0:
                self.logger.warning(f"베팅 금액이 너무 작아 클릭할 칩이 없습니다: {bet_amount}원")
                # 최소 금액(1000원) 베팅
                chip_clicks[1000] = 1
                total_clicks = 1
            
            # 베팅 대상 선택 (미리 요소 찾기)
            if bet_type == 'P':
                # Player 영역 찾기
                selector = "div.spot--5ad7f[data-betspot-destination='Player']"
                self.logger.info(f"Player 베팅 영역 찾는 중: {selector}")
            elif bet_type == 'B':
                # Banker 영역 찾기
                selector = "div.spot--5ad7f[data-betspot-destination='Banker']"
                self.logger.info(f"Banker 베팅 영역 찾는 중: {selector}")
            else:
                self.logger.error(f"잘못된 베팅 타입: {bet_type}")
                return False
            
            try:
                # 베팅 영역 요소 미리 찾기
                bet_element = WebDriverWait(self.devtools.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                
                # 요소가 활성화되어 있는지 확인
                is_active = 'active--dc7b3' in bet_element.get_attribute('class')
                if is_active:
                    self.logger.info(f"이미 {bet_type} 영역이 활성화되어 있습니다.")
            except Exception as e:
                self.logger.error(f"베팅 영역 찾기 중 오류: {e}")
                return False
            
            # 베팅 성공 여부 플래그
            is_bet_success = False
            
            # 각 칩별로 선택 후 베팅 영역 클릭 수행
            for chip_value, clicks in chip_clicks.items():
                try:
                    # 칩 선택 요소 찾기
                    chip_selector = f"div.chip--29b81[data-role='chip'][data-value='{chip_value}']"
                    chip_element = WebDriverWait(self.devtools.driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, chip_selector))
                    )
                    
                    # 칩 활성화 상태 확인
                    if "disabled" in chip_element.get_attribute("class") or not chip_element.is_enabled():
                        self.logger.warning(f"{chip_value:,}원 칩이 비활성화되어 있습니다. 배팅이 불가능합니다.")
                        return False
                    
                    # 칩 선택 (한 번만 클릭)
                    chip_element.click()
                    time.sleep(0.1)  # 클릭 후 딜레이
                    self.logger.info(f"{chip_value:,}원 칩 선택 완료")
                    
                    # 베팅 영역 여러 번 클릭
                    for i in range(clicks):
                        bet_element.click()
                        time.sleep(0.1)  # 클릭 후 딜레이
                        self.logger.info(f"{bet_type} 영역 {i+1}/{clicks}번째 클릭 완료")
                    
                except Exception as e:
                    self.logger.error(f"{chip_value:,}원 칩 선택 또는 베팅 영역 클릭 중 오류: {e}")
                    return False
            
            # 베팅 후 총 베팅 금액 변경 확인 (1.5초 대기)
            time.sleep(1)
            try:
                total_bet_element = self.devtools.driver.find_element(By.CSS_SELECTOR, "span[data-role='total-bet-label-value']")
                after_bet_amount_text = total_bet_element.text
                self.logger.info(f"베팅 후 총 베팅 금액: {after_bet_amount_text}")
                
                # 숫자만 추출
                after_bet_amount = int(after_bet_amount_text.replace('₩', '').replace(',', '').replace('⁩', '').replace('⁦', '').strip() or '0')
                
                # 베팅 금액이 0에서 변경되었는지 확인 (라운드마다 리셋되는 로직 반영)
                if after_bet_amount > 0:
                    self.logger.info(f"실제 베팅이 성공적으로 처리되었습니다. (금액: {after_bet_amount}원)")
                    is_bet_success = True
                else:
                    self.logger.warning(f"베팅 후에도 금액이 0원입니다. 실제 베팅이 이루어지지 않았습니다.")
                    is_bet_success = False
                    return False
            except Exception as e:
                self.logger.error(f"베팅 후 총 베팅 금액 확인 실패: {e}")
                is_bet_success = False
                return False
            
            # 베팅 상태 기록 (실제 베팅이 처리된 경우에만)
            if is_bet_success:
                self.has_bet_current_round = True
                self.current_bet_round = game_count  # 현재 게임 라운드 저장
                self.last_bet_type = bet_type        # 베팅한 타입 저장
                
                # UI 업데이트
                self.main_window.update_betting_status(
                    room_name=f"{current_room_name} (게임 수: {game_count}, 베팅: {bet_type})",
                    pick=bet_type  # PICK 값 직접 설정
                )
                
                return True
            else:
                return False
            
        except Exception as e:
            # 오류 로깅
            self.logger.error(f"베팅 중 오류 발생: {e}", exc_info=True)
            return False
        
    def reset_betting_state(self, new_round=None):
        """베팅 상태 초기화"""
        self.has_bet_current_round = False
        # 새 라운드가 지정되면 저장, 아니면 0으로 초기화
        self.current_bet_round = new_round if new_round is not None else 0
        self.last_bet_type = None
        self.logger.info(f"베팅 상태 초기화 완료 (라운드: {self.current_bet_round})")
    
    def check_is_bet_for_current_round(self, current_round):
        """현재 라운드에 베팅했는지 확인"""
        return self.has_bet_current_round and self.current_bet_round == current_round
    
    def check_betting_result(self, bet_type, latest_result, current_room_name, result_count, step=None):
        """
        베팅 결과를 직접 확인합니다.
        
        Args:
            bet_type (str): 베팅한 타입 ('P' 또는 'B')
            latest_result (str): 게임 결과 ('P', 'B', 'T')
            current_room_name (str): 현재 방 이름
            result_count (int): 결과 카운트
            step (int, optional): 현재 마틴 단계 (1부터 시작)
                
        Returns:
            tuple: (result_status, result_count)
            - result_status: 'win'(승리), 'lose'(패배), 'tie'(무승부)
        """
        try:
            # 마틴 단계가 None이면 현재 단계 가져오기
            if step is None:
                step = self.main_window.trading_manager.martin_service.current_step + 1  # 0부터 시작하므로 +1

            # 결과 번호 증가
            result_count += 1
            
            # 게임 결과가 'T'(타이)인 경우 무승부로 처리
            if latest_result == 'T':
                self.logger.info(f"게임 결과: 타이(T) - 무승부 처리")
                result_text = "무승부"
                result_status = "tie"  # 타이는 무승부로 처리
                marker = "T"
            else:
                # 베팅 타입과 게임 결과 비교
                if bet_type == latest_result:
                    result_status = "win"
                    result_text = "적중"
                    marker = "O"
                else:
                    result_status = "lose"
                    result_text = "실패"
                    marker = "X"
                self.logger.info(f"베팅 결과 확인 - 베팅: {bet_type}, 결과: {latest_result}, 승패: {result_text}, 단계: {step}")
            
            # UI에 결과 추가
            self.main_window.add_betting_result(
                no=result_count,
                room_name=current_room_name,
                step=step,
                result=result_text
            )
            
            # 해당 단계에 마커 설정
            self.main_window.update_betting_status(
                step_markers={step: marker}
            )
            
            return result_status, result_count
                
        except Exception as e:
            # 오류 로깅
            self.logger.error(f"베팅 결과 확인 중 오류 발생: {e}", exc_info=True)
            return "error", result_count

    def get_last_bet(self):
        """마지막 베팅 정보 반환"""
        if not self.has_bet_current_round:
            return None
        return {
            'round': self.current_bet_round,
            'type': self.last_bet_type
        }
        
    def update_balance_after_bet(self):
        """베팅 후 잔액 변경 확인 및 UI 업데이트"""
        try:
            # iframe 내에서 잔액 가져오기
            balance_element = self.devtools.driver.find_element(By.CSS_SELECTOR, "span[data-role='balance-label-value']")
            balance_text = balance_element.text
            
            # 숫자만 추출
            current_balance = int(balance_text.replace('₩', '').replace(',', '').replace('⁩', '').replace('⁦', '').strip() or '0')
            
            # 현재 금액 업데이트
            self.main_window.update_user_data(current_amount=current_balance)
            
            self.logger.info(f"현재 잔액 업데이트: {current_balance:,}원")
            
            return current_balance
        except Exception as e:
            self.logger.error(f"잔액 업데이트 실패: {e}")
            return None