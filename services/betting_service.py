# services/betting_service.py
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from utils.iframe_utils import IframeManager, switch_to_iframe_with_retry  # 추가: iframe 유틸리티 임포트

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
        
        # 추가: iframe 매니저 초기화
        self.iframe_manager = None

    def place_bet(self, bet_type, current_room_name, game_count, is_trading_active, bet_amount=None):
        self.logger.info(f"베팅 시도 - 타입: {bet_type}, 게임: {game_count}, 활성화: {is_trading_active}, 금액: {bet_amount}")

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
            if hasattr(self, 'last_bet_time'):
                elapsed = time.time() - self.last_bet_time
                if elapsed < 5.0:  # 5초 이내 재배팅 방지
                    self.logger.warning(f"마지막 배팅 후 {elapsed:.1f}초밖에 지나지 않았습니다. 최소 5초 대기가 필요합니다.")
                    return False
            
            # 자동 매매 활성화 상태 확인
            if not is_trading_active:
                self.logger.info("자동 매매가 활성화되지 않았습니다.")
                return False
            
            # 이미 베팅했는지 확인 (중복 베팅 방지)
            if self.has_bet_current_round:
                self.logger.info("이미 현재 라운드에 베팅했습니다.")
                return False
            
            # bet_type 검증 - P 또는 B만 허용
            if bet_type not in ['P', 'B']:
                self.logger.error(f"잘못된 베팅 타입: {bet_type}. 'P' 또는 'B'만 가능합니다.")
                return False
            
            # 중요: 입력받은 베팅 타입 기록 (디버깅 용)
            self.logger.info(f"[베팅] 베팅 타입 설정: {bet_type}, 게임 수: {game_count}")
            
            # 메모리 최적화 시도
            import gc
            gc.collect()
            time.sleep(0.5)  # 시스템에 최적화 시간 제공
            
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
                    self.logger.info("베팅: 중첩된 iframe이 발견되어 전환")
                    self.devtools.driver.switch_to.frame(nested_iframes[0])
            except Exception as e:
                self.logger.warning(f"베팅: iframe 전환 실패: {e}")
                self.devtools.driver.switch_to.default_content()
            
            # 방법 2: 실패 시 유틸리티 함수 사용
            if not iframe_switched:
                self.logger.info("베팅: 자동 iframe 전환 시도")
                iframe_switched = switch_to_iframe_with_retry(self.devtools.driver)
                
                if not iframe_switched:
                    self.logger.error("모든 iframe 전환 방법 실패")
                    return False

            # 칩 클릭 가능 여부로 베팅 상태 확인
            self.logger.info("베팅 가능 상태 확인 시작...")

            max_attempts = 30  # 최대 30초 대기 (2초 간격)
            attempts = 0
            chip_clickable = False

            while attempts < max_attempts:
                try:
                    # 1000원 칩 요소 찾기
                    chip_selector = "div.chip--29b81[data-role='chip'][data-value='1000']"
                    chip_elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, chip_selector)
                    
                    if chip_elements:
                        chip_element = chip_elements[0]
                        
                        # 칩이 표시되고 disabled 상태가 아닌지 확인
                        if chip_element.is_displayed():
                            chip_class = chip_element.get_attribute("class")
                            if "disabled" not in chip_class:
                                # 실제로 클릭 가능한지 테스트 (현재는 클릭하지 않고 클릭 가능성만 확인)
                                self.logger.info("1000원 칩 클릭 가능 상태 감지됨")
                                chip_clickable = True
                                
                                # 중요: 베팅 가능 상태가 되면 최신 게임 결과 다시 확인
                                try:
                                    # 게임 상태 다시 확인하여 최신 결과 업데이트
                                    game_state = self.main_window.trading_manager.game_monitoring_service.get_current_game_state(log_always=False)
                                    if game_state:
                                        latest_result = game_state.get('latest_result')
                                        self.logger.info(f"베팅 가능 상태 감지 후 최신 결과 재확인: {latest_result}")
                                        
                                        # 최신 결과가 있으면 엑셀에 반영
                                        if latest_result:
                                            # 엑셀 트레이딩 서비스를 통해 결과 처리
                                            result = self.main_window.trading_manager.excel_trading_service.process_game_results(
                                                game_state, 
                                                self.main_window.trading_manager.game_count, 
                                                self.main_window.trading_manager.current_room_name,
                                                log_on_change=True
                                            )
                                            
                                            # 결과 처리 성공 시 게임 카운트와 PICK 값 업데이트
                                            if result[0] is not None:
                                                last_column, new_game_count, recent_results, next_pick = result
                                                if new_game_count > self.main_window.trading_manager.game_count:
                                                    self.logger.info(f"게임 카운트 업데이트: {self.main_window.trading_manager.game_count} -> {new_game_count}")
                                                    # 이전 게임 결과 처리
                                                    self.main_window.trading_manager._process_previous_game_result(game_state, new_game_count)
                                                    # 게임 카운트 업데이트
                                                    self.main_window.trading_manager.game_count = new_game_count
                                                    
                                                    # 새로운 PICK 값이 있으면 현재 PICK 값 업데이트 및 UI 갱신
                                                    if next_pick in ['P', 'B']:
                                                        self.logger.info(f"최신 PICK 값 업데이트: {next_pick}")
                                                        self.main_window.trading_manager.current_pick = next_pick
                                                        self.main_window.update_betting_status(pick=next_pick)
                                                        # PICK 값 변경에 따라 베팅 타입 업데이트
                                                        bet_type = next_pick
                                except Exception as e:
                                    self.logger.error(f"베팅 가능 상태 후 최신 결과 확인 중 오류: {e}")
                                
                                break
                        
                    self.logger.info(f"베팅 가능 상태 대기 중... 시도: {attempts+1}/{max_attempts}")
                    attempts += 1
                    time.sleep(2)
                    
                except Exception as e:
                    self.logger.warning(f"칩 클릭 가능 상태 확인 중 오류: {e}")
                    attempts += 1
                    time.sleep(1)
            
            if not chip_clickable:
                self.logger.warning("베팅 가능 상태 대기 시간 초과. 칩이 클릭 가능 상태가 되지 않았습니다.")
                return False
            
            # 현재 게임 상태 확인 (추가 정보용)
            try:
                # 게임 상태 표시 요소 확인
                game_status_element = self.devtools.driver.find_element(By.CSS_SELECTOR, "div[data-role='game-status']")
                game_status_text = game_status_element.text if game_status_element else ""
                self.logger.info(f"현재 게임 상태: {game_status_text}")
            except Exception as e:
                pass
                # 게임 상태 확인 실패는 무시 (이미 칩으로 확인함)
            
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
                self.logger.info(f"{bet_type} 베팅 영역 찾기 시도...")

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
            
            # 베팅 후 총 베팅 금액 변경 확인
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
                
                # 로그에 베팅 정보 명확하게 기록 (디버깅용)
                self.logger.info(f"[베팅완료] 라운드: {game_count}, 베팅타입: {bet_type}")
                
                # 방 이름에서 첫 번째 줄만 추출 (UI 표시용)
                display_room_name = current_room_name.split('\n')[0] if '\n' in current_room_name else current_room_name
                
                # UI 업데이트
                self.main_window.update_betting_status(
                    room_name=f"{display_room_name} (게임 수: {game_count}, 베팅: {bet_type})",
                    pick=bet_type  # PICK 값 직접 설정
                )
                
                self.last_bet_time = time.time()
                return True
            else:
                return False
            
        except Exception as e:
            # 오류 로깅
            self.logger.error(f"베팅 중 오류 발생: {e}", exc_info=True)
            return False
            
    def reset_betting_state(self, new_round=None):
        """베팅 상태 초기화"""
        self.has_bet_current_round = False  # 항상 False로 초기화
        # 새 라운드가 지정되면 저장, 아니면 0으로 초기화
        self.current_bet_round = new_round if new_round is not None else 0
        self.last_bet_type = None
        self.logger.info(f"베팅 상태 완전 초기화 완료 (라운드: {self.current_bet_round})")
        

    def check_is_bet_for_current_round(self, current_round):
        """현재 라운드에 베팅했는지 확인"""
        # 무승부 발생 시 베팅 상태가 초기화된 경우를 처리
        if self.has_bet_current_round == False and self.current_bet_round != current_round:
            self.logger.info(f"[INFO] 새 라운드({current_round}) 감지, 이전 베팅 기록({self.current_bet_round}) 초기화")
            self.current_bet_round = current_round
            return False
            
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
                    self.logger.info("잔액 확인: 중첩된 iframe이 발견되어 전환")
                    self.devtools.driver.switch_to.frame(nested_iframes[0])
            except Exception as e:
                self.logger.warning(f"잔액 확인: iframe 전환 실패: {e}")
                self.devtools.driver.switch_to.default_content()
            
            # 방법 2: 실패 시 유틸리티 함수 사용
            if not iframe_switched:
                self.logger.info("잔액 확인: 자동 iframe 전환 시도")
                iframe_switched = switch_to_iframe_with_retry(self.devtools.driver)
                
                if not iframe_switched:
                    self.logger.error("모든 iframe 전환 방법 실패")
                    return None
                    
            # iframe 내에서 잔액 가져오기
            balance_element = self.devtools.driver.find_element(By.CSS_SELECTOR, "span[data-role='balance-label-value']")
            balance_text = balance_element.text
            
            # 숫자만 추출
            current_balance = int(balance_text.replace('₩', '').replace(',', '').replace('⁩', '').replace('⁦', '').strip() or '0')
            
            # 현재 금액 업데이트
            self.main_window.update_user_data(current_amount=current_balance)
            
            self.logger.info(f"현재 잔액 업데이트: {current_balance:,}원")
            
            # 기본 컨텐츠로 돌아가기
            self.devtools.driver.switch_to.default_content()
            
            return current_balance
        except Exception as e:
            self.logger.error(f"잔액 업데이트 실패: {e}")
            
            # 기본 컨텐츠로 돌아가기 시도
            try:
                self.devtools.driver.switch_to.default_content()
            except:
                pass
                
            return None