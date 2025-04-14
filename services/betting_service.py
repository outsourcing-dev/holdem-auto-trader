# services/betting_service.py 리팩토링
import logging
import random
import time
import gc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.iframe_utils import switch_to_iframe_with_retry, find_element_in_iframes

class BettingService:
    def __init__(self, devtools, main_window, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        self.devtools = devtools
        self.main_window = main_window
        self.has_bet_current_round = False
        self.current_bet_round = 0
        self.last_bet_type = None
        self.last_bet_time = 0

        self.bet_result_confirmed = False
        self.last_bet_result = None
        self.last_bet_time = 0
        
    # 사용되지 않음. 필요시 수동 클릭 디버깅용
    def _click_element_randomly(self, element, element_name="", mode="default"):
        try:
            if not hasattr(element, 'location_once_scrolled_into_view'):
                raise ValueError("WebElement가 아님")

            location = element.location_once_scrolled_into_view
            size = element.size
            self.logger.info(f"[디버그] {element_name} size: width={size['width']}, height={size['height']}")

            width = int(size['width'])
            height = int(size['height'])

            offset_x = width // 2
            offset_y = height // 2

            self.logger.info(f"[정타 클릭] 위치: offset_x={offset_x}, offset_y={offset_y}")

            actions = ActionChains(self.devtools.driver)
            actions.move_to_element_with_offset(element, offset_x, offset_y).click().perform()
            return True
        except Exception as e:
            self.logger.warning(f"{element_name} 정타 클릭 시도 실패: {e}")
            return False

    def _safe_click(self, element, element_name=""):
        try:
            if not hasattr(element, 'location_once_scrolled_into_view'):
                self.logger.error(f"{element_name}은(는) 유효한 WebElement가 아닙니다: {type(element)}")
                return False

            # 스크롤 먼저 이동
            self.devtools.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.2)

            # JS로 클릭
            self.logger.info(f"[JS 클릭] {element_name}에 대해 JS 클릭 시도")
            self.devtools.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e:
            self.logger.error(f"{element_name} JS 클릭 실패: {e}")
            return False
        
    def place_bet(self, bet_type, current_room_name, game_count, is_trading_active, bet_amount=None):
        """베팅 타입에 따라 적절한 베팅 영역을 클릭"""
        self.logger.info(f"베팅 시도 - 타입: {bet_type}, 게임: {game_count}, 금액: {bet_amount}")

        try:
            # 1. 베팅 전 유효성 검사
            if not self._validate_bet_conditions(bet_type, is_trading_active):
                return False
            
            self.current_bet_round = game_count

            # 2. 메모리 최적화
            gc.collect()
            
            # 3. iframe 전환
            if not switch_to_iframe_with_retry(self.devtools.driver, max_retries=5, max_depth=3):
                self.logger.error("베팅: iframe 전환 실패, 베팅 진행 불가")
                return False

            # 4. 베팅 가능 상태 확인
            if not self._wait_for_betting_available():
                return False
            
            # ✅ 베팅 직전: 위젯 마커가 'O'이면 마커 리셋
            if hasattr(self.main_window, 'betting_widget'):
                marker = None
                if hasattr(self.main_window.betting_widget, 'get_current_marker'):
                    marker = self.main_window.betting_widget.get_current_marker()
                
                if marker == "O":
                    self.logger.info("베팅 직전: 위젯 마커 'O' 확인됨 → 마커 초기화")
                    self.main_window.betting_widget.reset_step_markers()
                    self.main_window.betting_widget.room_position_counter = 0
            
            # 5. 베팅 실행
            bet_success = self._execute_betting(bet_type, bet_amount)
            
            # 6. 결과 처리
            if bet_success:
                self._handle_successful_bet(bet_type, game_count, current_room_name)
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"베팅 중 오류 발생: {e}", exc_info=True)
            return False
            
    def _validate_bet_conditions(self, bet_type, is_trading_active):
        """베팅 전 조건 검증"""
        # 최근 베팅 후 최소 시간 확인
        if hasattr(self, 'last_bet_time'):
            elapsed = time.time() - self.last_bet_time
            if elapsed < 5.0:
                self.logger.warning(f"마지막 배팅 후 {elapsed:.1f}초밖에 지나지 않았습니다. 최소 5초 대기 필요.")
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
            
        return True

    def _wait_for_betting_available(self):
        """베팅 가능 상태가 될 때까지 대기"""
        self.logger.info("베팅 가능 상태 확인 시작...")
        max_attempts = 60  # 최대 60초 대기 (1초 간격)
        
        for attempt in range(max_attempts):
            try:
                # 여러 선택자로 1000원 칩 요소 찾기 시도
                chip_selectors = [
                    "div.chip--29b81[data-role='chip'][data-value='1000']",
                    "div[data-role='chip'][data-value='1000']",
                    "div.chip[data-value='1000']"
                ]
                
                for selector in chip_selectors:
                    chip_elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                    if chip_elements and len(chip_elements) > 0:
                        chip_element = chip_elements[0]
                        if chip_element.is_displayed():
                            # 클릭 가능한 상태인지 확인 (disabled 클래스가 없는지)
                            chip_class = chip_element.get_attribute("class")
                            if "disabled" not in chip_class:
                                self.logger.info("베팅 가능 상태 감지됨")
                                self._update_game_state()
                                return True
                
                self.logger.info(f"베팅 가능 상태 대기 중... 시도: {attempt+1}/{max_attempts}")
                time.sleep(1)
            except Exception as e:
                self.logger.warning(f"칩 클릭 가능 상태 확인 중 오류: {e}")
                time.sleep(1)
        
        self.logger.warning("베팅 가능 상태 대기 시간 초과.")
        return False

    def _update_game_state(self):
        """베팅 가능 상태 감지 후 최신 결과 업데이트"""
        try:
            # 게임 상태 다시 확인하여 최신 결과 업데이트
            game_state = self.main_window.trading_manager.game_monitoring_service.get_current_game_state(log_always=False)
            if not game_state:
                return

            latest_result = game_state.get('latest_result')
            self.logger.info(f"베팅 가능 상태 감지 후 최신 결과 재확인: {latest_result}")
            
            # 최신 결과가 있으면 엑셀에 반영
            if latest_result:
                # 현재 게임 카운트 저장
                current_game_count = self.main_window.trading_manager.game_count
                
                result = self.main_window.trading_manager.excel_trading_service.process_game_results(
                    game_state, 
                    current_game_count,
                    self.main_window.trading_manager.current_room_name,
                    log_on_change=True
                )
                
                if result[0] is not None:
                    last_column, new_game_count, recent_results, next_pick = result
                    
                    # 게임 카운트가 한 단계만 증가했는지 확인 (안전 장치)
                    if new_game_count > current_game_count and new_game_count <= current_game_count + 1:
                        self.logger.info(f"게임 카운트 업데이트: {current_game_count} → {new_game_count}")
                        
                        # game 속성 대신 game_helper 사용 
                        if hasattr(self.main_window.trading_manager, 'game_helper'):
                            self.main_window.trading_manager.game_helper.process_previous_game_result(game_state, new_game_count)
                        
                        # 게임 카운트 업데이트
                        self.main_window.trading_manager.game_count = new_game_count
                        
                        # 새로운 PICK 값이 있으면 현재 PICK 값 업데이트 및 UI 갱신
                        if next_pick in ['P', 'B']:
                            self.main_window.trading_manager.current_pick = next_pick
                            self.main_window.update_betting_status(pick=next_pick)
                    else:
                        # 갑자기 게임 카운트가 2 이상 증가한 경우 경고 로그
                        if new_game_count > current_game_count + 1:
                            self.logger.warning(f"게임 카운트가 비정상적으로 증가: {current_game_count} → {new_game_count}")
                            # 안전하게 1씩만 증가시킴
                            self.main_window.trading_manager.game_count = current_game_count + 1
        except Exception as e:
            self.logger.warning(f"베팅 가능 상태 후 최신 결과 확인 중 오류: {e}")
            
    def _find_betting_area(self, bet_type):
        """베팅 영역 찾기"""
        if bet_type == 'P':
            # Player 영역 찾기
            player_selectors = [
                "div.spot--5ad7f[data-betspot-destination='Player']",
                "div[data-betspot-destination='Player']",
                "div.player-bet-spot",
                "div.bet-spot-player",
                "div[data-type='player']",
                "div.bet-spot[data-type='Player']",
                "div.bet-area-player",
                "div.bet-area[data-role='player']"
            ]
            
            self.logger.info(f"Player 베팅 영역 찾는 중...")
            for selector in player_selectors:
                try:
                    elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and elements[0].is_displayed():
                        return elements[0]
                except:
                    continue
            
            # XPath로 시도
            xpath_expressions = [
                "//div[contains(@class, 'spot') and contains(@*, 'Player')]",
                "//div[contains(@class, 'player') or contains(@class, 'Player')]",
                "//div[contains(text(), 'Player') and (contains(@class, 'bet') or contains(@class, 'spot'))]"
            ]
            
            for xpath in xpath_expressions:
                try:
                    elements = self.devtools.driver.find_elements(By.XPATH, xpath)
                    if elements and elements[0].is_displayed():
                        return elements[0]
                except:
                    continue
                    
        elif bet_type == 'B':
            # Banker 영역 찾기
            banker_selectors = [
                "div.spot--5ad7f[data-betspot-destination='Banker']",
                "div[data-betspot-destination='Banker']",
                "div.banker-bet-spot",
                "div.bet-spot-banker",
                "div[data-type='banker']",
                "div.bet-spot[data-type='Banker']",
                "div.bet-area-banker",
                "div.bet-area[data-role='banker']"
            ]
            
            self.logger.info(f"Banker 베팅 영역 찾는 중...")
            for selector in banker_selectors:
                try:
                    elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and elements[0].is_displayed():
                        return elements[0]
                except:
                    continue
            
            # XPath로 시도
            xpath_expressions = [
                "//div[contains(@class, 'spot') and contains(@*, 'Banker')]",
                "//div[contains(@class, 'banker') or contains(@class, 'Banker')]",
                "//div[contains(text(), 'Banker') and (contains(@class, 'bet') or contains(@class, 'spot'))]"
            ]
            
            for xpath in xpath_expressions:
                try:
                    elements = self.devtools.driver.find_elements(By.XPATH, xpath)
                    if elements and elements[0].is_displayed():
                        return elements[0]
                except:
                    continue
        
        # 최후의 수단: iframe_utils의 find_element_in_iframes 사용
        self.logger.info(f"기본 방법으로 {bet_type} 베팅 영역을 찾지 못함. 고급 검색 시도...")
        # 'timeout' 매개변수 제거
        success, element = find_element_in_iframes(
            self.devtools.driver,
            By.XPATH, 
            f"//div[contains(@*, '{bet_type}') and (contains(@class, 'spot') or contains(@class, 'bet'))]",
            max_depth=3
        )
        
        if success:
            return element
            
        return None

    def _find_chip(self, chip_value):
        """칩 찾기"""
        # 여러 선택자로 칩 찾기
        chip_selectors = [
            f"div.chip--29b81[data-role='chip'][data-value='{chip_value}']",
            f"div[data-role='chip'][data-value='{chip_value}']",
            f"div.chip[data-value='{chip_value}']"
        ]
        
        for selector in chip_selectors:
            try:
                elements = WebDriverWait(self.devtools.driver, 3).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                if elements and len(elements) > 0 and elements[0].is_displayed():
                    return elements[0]
            except:
                continue
        
        # XPath 사용
        try:
            xpath = f"//div[contains(@class, 'chip') and @data-value='{chip_value}']"
            elements = self.devtools.driver.find_elements(By.XPATH, xpath)
            if elements and len(elements) > 0 and elements[0].is_displayed():
                return elements[0]
        except:
            pass
        
        return None

    def _execute_betting(self, bet_type, bet_amount=None):
        """베팅 실행"""
        bet_element = self._find_betting_area(bet_type)
        if not bet_element:
            self.logger.error(f"{bet_type} 베팅 영역을 찾을 수 없음")
            return False

        if bet_amount is None:
            bet_amount = self.main_window.trading_manager.martin_service.get_current_bet_amount()

        self.logger.info(f"현재 베팅 금액: {bet_amount:,}원")

        available_chips = [500000, 100000, 25000, 5000, 1000]
        chip_clicks = {}
        remaining = bet_amount

        for chip in available_chips:
            count = remaining // chip
            if count > 0:
                chip_clicks[chip] = count
                remaining %= chip

        if not chip_clicks:
            chip_clicks[1000] = 1
            self.logger.warning("1000원 칩으로 기본 배팅 시도")

        self.logger.info(f"베팅 금액 {bet_amount:,}원 -> 칩별 클릭 횟수: {chip_clicks}")
        bet_successful = False

        for chip_value, clicks in chip_clicks.items():
            chip_element = self._find_chip(chip_value)
            if not chip_element:
                self.logger.warning(f"{chip_value}원 칩을 찾지 못함")
                continue

            if "disabled" in chip_element.get_attribute("class") or not chip_element.is_enabled():
                self.logger.warning(f"{chip_value:,}원 칩이 비활성화 상태입니다.")
                continue

            # 칩 클릭 시도 (우선 일반 클릭, 실패 시 JS)
            try:
                time.sleep(0.5)
                try:
                    chip_element.click()
                    self.logger.info(f"[클릭] {chip_value:,}원 칩 클릭 성공")
                except Exception as e:
                    self.logger.warning(f"{chip_value:,}원 칩 일반 클릭 실패 → JS 클릭 시도")
                    self.devtools.driver.execute_script("arguments[0].click();", chip_element)
                    self.logger.info(f"[JS 클릭] {chip_value:,}원 칩 클릭 완료")
                time.sleep(0.5)
            except Exception as e:
                self.logger.error(f"{chip_value}원 칩 클릭 실패: {e}")
                continue

            for i in range(clicks):
                try:
                    time.sleep(0.2)
                    try:
                        bet_element.click()
                        self.logger.info(f"{bet_type} 영역 {i+1}/{clicks} 클릭 완료")
                    except Exception as e:
                        self.logger.warning(f"{bet_type} 영역 일반 클릭 실패 → JS 클릭")
                        self.devtools.driver.execute_script("arguments[0].click();", bet_element)
                        self.logger.info(f"{bet_type} 영역 JS 클릭 완료 ({i+1}/{clicks})")
                    bet_successful = True
                except Exception as e:
                    self.logger.error(f"베팅 클릭 중 오류 발생: {e}")
                    continue

        if bet_successful:
            time.sleep(1.5)
            amount_after = self._get_current_bet_amount()
            if amount_after == bet_amount:
                self.logger.info(f"[성공] 베팅 금액 확인됨: {amount_after}원")
                return True
            else:
                self.logger.warning(f"[실패] UI 표시 베팅 금액({amount_after}원)이 기대값({bet_amount}원)과 다릅니다.")
                return False
        else:
            self.logger.warning("베팅 클릭이 한 번도 성공하지 않았습니다.")
            return False
        
    def _get_current_bet_amount(self):
        """현재 베팅 금액 조회"""
        try:
            # 베팅 금액 요소 찾기
            bet_amount_selectors = [
                "span[data-role='total-bet-label-value']",
                "div[data-role='total-bet'] span",
                "div.total-bet-amount",
                "span.bet-amount"
            ]
            
            for selector in bet_amount_selectors:
                elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and len(elements) > 0:
                    total_bet_element = elements[0]
                    amount_text = total_bet_element.text
                    # 숫자만 추출
                    return int(''.join(filter(str.isdigit, amount_text)) or '0')
            
            return 0
        except Exception as e:
            self.logger.warning(f"베팅 금액 확인 실패: {e}")
            return 0

    # services/betting_service.py의 _handle_successful_bet 메서드 수정 또는 확장

    def _handle_successful_bet(self, bet_type, game_count, current_room_name):
        """성공한 베팅 처리"""
        self.has_bet_current_round = True
        self.current_bet_round = game_count  # 현재 게임 라운드 저장
        self.last_bet_type = bet_type        # 베팅한 타입 저장
        self.last_bet_time = time.time()
        
        # 로그에 베팅 정보 기록
        self.logger.info(f"[베팅완료] 라운드: {game_count}, 베팅타입: {bet_type}")
        
        # 방 이름에서 첫 번째 줄만 추출 (UI 표시용)
        display_room_name = current_room_name.split('\n')[0] if '\n' in current_room_name else current_room_name
        
        # 마틴 단계 확인 및 동기화
        martin_step = 0
        if hasattr(self.main_window, 'trading_manager') and hasattr(self.main_window.trading_manager, 'martin_service'):
            martin_step = self.main_window.trading_manager.martin_service.current_step
            
            # 베팅 위젯의 위치 카운터 동기화 (위젯이 있는 경우)
            if hasattr(self.main_window, 'betting_widget'):
                self.main_window.betting_widget.room_position_counter = martin_step
                self.logger.info(f"베팅 위젯 위치 카운터를 마틴 단계({martin_step+1})와 동기화")
        
        # UI 업데이트
        self.main_window.update_betting_status(
            room_name=f"{display_room_name}",
            pick=bet_type  # PICK 값 직접 설정
        )
        
    def reset_betting_state(self, new_round=None):
        """베팅 상태 초기화"""
        previous_round = self.current_bet_round
        self.has_bet_current_round = False  # 항상 False로 초기화
        # 새 라운드가 지정되면 저장, 아니면 0으로 초기화
        self.current_bet_round = new_round if new_round is not None else 0
        self.bet_result_confirmed = False   # 결과 확인 여부 초기화
        self.last_bet_result = None         # 마지막 결과 초기화
        # self.logger.info(f"베팅 상태 초기화 완료 (라운드: {previous_round} → {self.current_bet_round})")

    def check_is_bet_for_current_round(self, current_round):
        """현재 라운드에 베팅했는지 확인"""
        # 무승부 발생 시 베팅 상태가 초기화된 경우를 처리
        if self.has_bet_current_round == False and self.current_bet_round != current_round:
            self.logger.info(f"새 라운드({current_round}) 감지, 이전 베팅 기록({self.current_bet_round}) 초기화")
            self.current_bet_round = current_round
            return False
            
        return self.has_bet_current_round and self.current_bet_round == current_round
    
    def check_betting_result(self, bet_type, latest_result, current_room_name, result_count, step=None):
        """베팅 결과 확인"""
        try:
            # 마틴 단계가 None이면 현재 단계 가져오기
            if step is None:
                step = self.main_window.trading_manager.martin_service.current_step + 1

            # 결과 번호 증가
            result_count += 1
            
            # 게임 결과가 'T'(타이)인 경우 무승부로 처리
            if latest_result == 'T':
                self.logger.info(f"게임 결과: 타이(T) - 무승부 처리")
                result_text = "무승부"
                result_status = "tie"
                marker = "T"
                
                # 타이 결과 시 베팅 상태 초기화
                self.has_bet_current_round = False
                self.logger.info(f"타이(T) 결과로 베팅 상태 초기화: 같은 방에서 재베팅 가능")
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