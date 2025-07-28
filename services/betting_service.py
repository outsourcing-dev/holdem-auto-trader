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
from utils.trading_manager_helpers import get_widget_position

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
        
    # BettingService의 place_bet 메서드에서 타이 직후 처리 수정

    def place_bet(self, bet_type, current_room_name, game_count, is_trading_active, bet_amount=None):
        self.logger.info(f"베팅 시도 - 타입: {bet_type}, 게임: {game_count}, 금액: {bet_amount}")

        try:
            if not self._validate_bet_conditions(bet_type, is_trading_active):
                return False

            self.current_bet_round = game_count
            gc.collect()

            if not switch_to_iframe_with_retry(self.devtools.driver, max_retries=5, max_depth=3):
                self.logger.error("베팅: iframe 전환 실패, 베팅 진행 불가")
                return False

            if not self._wait_for_betting_available():
                return False

            # 위젯 마커 초기화 로직
            if hasattr(self.main_window, 'betting_widget'):
                marker = getattr(self.main_window.betting_widget, 'get_current_marker', lambda: None)()
                if marker == "O":
                    self.logger.info("베팅 직전: 위젯 마커 'O' 감지 → 마커 초기화")
                    self.main_window.betting_widget.reset_step_markers()
                    self.main_window.betting_widget.room_position_counter = 0

            # 타이 직후 처리 로직 제거 또는 수정
            had_tie_last_round = getattr(self.main_window.trading_manager, 'had_tie_last_round', False)
            
            if had_tie_last_round:
                self.logger.info("타이 직후 베팅: 동일 위치 유지")
                # 타이 직후에는 베팅 타입 변경하지 않음 (서버에서 이미 적절한 예측을 제공함)
                # 타이 직후 플래그 초기화
                self.main_window.trading_manager.had_tie_last_round = False

            bet_success = self._execute_betting(bet_type, bet_amount)

            if bet_success:
                self._handle_successful_bet(bet_type, game_count, current_room_name)
                self.has_bet_current_round = True
                return True
            else:
                return False

        except Exception as e:
            self.logger.error(f"베팅 중 오류 발생: {e}", exc_info=True)
            return False

    # _update_game_state 메서드는 아예 제거하거나 매우 단순화
    def _update_game_state(self):
        """베팅 가능 상태 감지 후 간단한 상태 업데이트만"""
        try:
            # 여기서는 게임 결과 처리를 하지 않음!
            # 단순히 UI 업데이트나 기본적인 상태 확인만 수행
            self.logger.debug("베팅 가능 상태 감지 완료 - 게임 결과 처리는 별도로 진행")
            
        except Exception as e:
            self.logger.warning(f"상태 업데이트 중 오류: {e}")
            

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

    # BettingService의 _wait_for_betting_available 메서드도 수정
    def _wait_for_betting_available(self):
        """베팅 가능 상태가 될 때까지 대기 - 게임 결과 처리 제거"""
        self.logger.info("베팅 가능 상태 확인 시작...")
        max_attempts = 60  # 최대 60초 대기
        
        for attempt in range(max_attempts):
            try:
                # 칩 활성화 확인만 수행
                chip_selectors = [
                    "div.chip--29b81[data-role='chip']",
                    "div[data-role='chip']",
                    "div.chip[data-value]"
                ]
                
                chip_active = False
                for selector in chip_selectors:
                    chip_elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for chip_element in chip_elements:
                        if chip_element.is_displayed():
                            chip_class = chip_element.get_attribute("class") or ""
                            if "disabled" not in chip_class.lower():
                                chip_active = True
                                chip_value = chip_element.get_attribute("data-value")
                                self.logger.info(f"활성화된 칩 발견: {chip_value}원")
                                break
                    
                    if chip_active:
                        break
                
                if chip_active:
                    self.logger.info("베팅 가능 상태 감지됨 (활성화된 칩 발견)")
                    # _update_game_state() 호출 제거! 여기서 게임 결과 처리하지 않음
                    return True
                
                time.sleep(1)
            except Exception as e:
                self.logger.warning(f"칩 활성화 상태 확인 중 오류: {e}")
                time.sleep(0.5)
        
        self.logger.warning("베팅 가능 상태 대기 시간 초과.")
        return False


    def _find_chip(self, chip_value):
        """칩 찾기 - 개선된 버전"""
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
                
                for element in elements:
                    if element.is_displayed():
                        # 비활성화 상태 체크 (클래스와 속성 모두 확인)
                        chip_class = element.get_attribute("class") or ""
                        is_disabled = element.get_attribute("disabled")
                        
                        if "disabled" not in chip_class.lower() and not is_disabled:
                            return element
            except:
                continue
        
        # XPath 사용 - 비활성화되지 않은 칩만 찾기
        try:
            xpath = f"//div[contains(@class, 'chip') and @data-value='{chip_value}' and not(contains(@class, 'disabled'))]"
            elements = self.devtools.driver.find_elements(By.XPATH, xpath)
            
            for element in elements:
                if element.is_displayed():
                    return element
        except:
            pass
        
        return None

    def _get_available_chip_values(self):
        """사용 가능한 칩 값들을 동적으로 가져오기"""
        try:
            chip_selectors = [
                "div.chip--29b81[data-role='chip']",
                "div[data-role='chip']",
                "div.chip[data-value]"
            ]
            
            available_chips = []
            
            for selector in chip_selectors:
                chip_elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for chip_element in chip_elements:
                    if chip_element.is_displayed():
                        chip_class = chip_element.get_attribute("class") or ""
                        chip_value = chip_element.get_attribute("data-value")
                        
                        # 비활성화되지 않고 값이 있는 칩만 추가
                        if "disabled" not in chip_class.lower() and chip_value:
                            try:
                                available_chips.append(int(chip_value))
                            except ValueError:
                                continue
            
            # 중복 제거하고 내림차순 정렬
            available_chips = sorted(list(set(available_chips)), reverse=True)
            self.logger.info(f"사용 가능한 칩 값들: {available_chips}")
            return available_chips
            
        except Exception as e:
            self.logger.warning(f"사용 가능한 칩 값 조회 실패: {e}")
            # 기본값 반환 (기존 하드코딩된 값들)
            return [500000, 100000, 50000, 25000, 10000, 5000, 1000]

    def _execute_betting(self, bet_type, bet_amount=None):
        """베팅 실행 - 동적 칩 감지 적용"""
        bet_element = self._find_betting_area(bet_type)
        if not bet_element:
            self.logger.error(f"{bet_type} 베팅 영역을 찾을 수 없음")
            return False

        # 베팅 전 레이블 확인
        initial_label = self._check_betting_label()
        self.logger.info(f"베팅 전 레이블: {initial_label}")
        
        self.logger.info(f"현재 베팅 금액: {bet_amount:,}원")

        # 동적으로 사용 가능한 칩 값들 가져오기
        available_chips = self._wait_for_active_chips(max_wait=60, interval=1)
        if not available_chips:
            self.logger.error("사용 가능한 칩이 없습니다. 베팅을 중단합니다.")
            return False

        # 베팅 금액에 따른 칩 조합 계산
        chip_clicks = {}
        remaining = bet_amount

        for chip in available_chips:
            count = remaining // chip
            if count > 0:
                chip_clicks[chip] = count
                remaining %= chip

        # 칩 조합이 없으면 가장 작은 칩으로 기본 베팅
        if not chip_clicks and available_chips:
            smallest_chip = min(available_chips)
            chip_clicks[smallest_chip] = 1
            self.logger.warning(f"{smallest_chip}원 칩으로 기본 배팅 시도")
        elif not available_chips:
            self.logger.error("사용 가능한 칩이 없습니다.")
            return False

        self.logger.info(f"베팅 금액 {bet_amount:,}원 -> 칩별 클릭 횟수: {chip_clicks}")
        bet_successful = False

        for chip_value, clicks in chip_clicks.items():
            chip_element = self._find_chip(chip_value)
            if not chip_element:
                self.logger.warning(f"{chip_value}원 칩을 찾지 못함")
                continue

            # 칩 클릭 시도
            try:
                time.sleep(0.2)
                try:
                    chip_element.click()
                    self.logger.info(f"[클릭] {chip_value:,}원 칩 클릭 성공")
                except Exception as e:
                    self.logger.warning(f"{chip_value:,}원 칩 일반 클릭 실패 → JS 클릭 시도")
                    self.devtools.driver.execute_script("arguments[0].click();", chip_element)
                time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"{chip_value}원 칩 클릭 실패: {e}")
                continue

            for i in range(clicks):
                try:
                    time.sleep(0.1)
                    try:
                        bet_element.click()
                    except Exception as e:
                        self.logger.warning(f"{bet_type} 영역 일반 클릭 실패 → JS 클릭")
                        self.devtools.driver.execute_script("arguments[0].click();", bet_element)
                    bet_successful = True
                except Exception as e:
                    self.logger.error(f"베팅 클릭 중 오류 발생: {e}")
                    continue

        if bet_successful:
            time.sleep(1.0)
            current_label = self._check_betting_label()
            amount_after = self._get_current_bet_amount()
            
            self.logger.info(f"베팅 후 레이블: {current_label}, 금액: {amount_after:,}원")
            
            # "총 베팅금" 레이블이 있으면 베팅 성공으로 판단
            if current_label == "총 베팅금":
                self.logger.info(f"[성공] 베팅 확인: 레이블={current_label}, 금액={amount_after:,}원")
                return True
            elif current_label == "지난 우승":
                self.logger.warning(f"[실패] 베팅 시간 종료: 현재 레이블은 '{current_label}'")
                return False
            elif amount_after == bet_amount:
                self.logger.info(f"[성공] 레이블은 예상과 다르지만({current_label}) 베팅 금액 확인됨: {amount_after:,}원")
                return True
            else:
                self.logger.warning(f"[실패] 예상된 베팅 상태가 아님: 레이블={current_label}, 금액={amount_after:,}원 (기대값: {bet_amount:,}원)")
                return False
        else:
            self.logger.warning("베팅 클릭이 한 번도 성공하지 않았습니다.")
            return False
  
    def _find_betting_area(self, bet_type):
        """베팅 영역 찾기 - 실제 HTML 구조에 맞게 업데이트"""
        if bet_type == 'P':
            # Player 영역 찾기 - 더 안정적인 선택자로 개선
            player_selectors = [
                # 1순위: 가장 명확하고 안정적인 선택자
                "div.spot--5ad7f[data-betspot-destination='Player']",
                
                # 2순위: 그 다음으로 안정적인 선택자
                "div.content--e4fdb.player--2c620",
                
                # 3순위 (기존 호환성)
                "div.player--2c620",
                "div[data-betspot-destination='Player']",
            ]
            
            self.logger.info(f"Player 베팅 영역 찾는 중...")
            for selector in player_selectors:
                try:
                    elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and elements[0].is_displayed():
                        self.logger.info(f"Player 베팅 영역 찾음: {selector}")
                        return elements[0]
                except Exception as e:
                    self.logger.debug(f"선택자 '{selector}' 실패: {e}")
                    continue
            
            # XPath로 시도 (Player용) - 후순위
            xpath_expressions = [
                "//div[contains(@class, 'player--') and contains(@class, 'content--')]",
                "//div[contains(@data-betspot-destination, 'Player')]"
            ]
            
            for xpath in xpath_expressions:
                try:
                    elements = self.devtools.driver.find_elements(By.XPATH, xpath)
                    if elements and elements[0].is_displayed():
                        self.logger.info(f"Player 베팅 영역 찾음 (XPath): {xpath}")
                        return elements[0]
                except Exception as e:
                    self.logger.debug(f"XPath '{xpath}' 실패: {e}")
                    continue
                    
        elif bet_type == 'B':
            # Banker 영역 찾기 - 더 안정적인 선택자로 개선
            banker_selectors = [
                # 1순위: 가장 명확하고 안정적인 선택자
                "div.spot--5ad7f[data-betspot-destination='Banker']",
                
                # 2순위: 그 다음으로 안정적인 선택자
                "div.content--e4fdb.banker--6b486",

                # 3순위 (기존 호환성)
                "div.banker--6b486",
                "div[data-betspot-destination='Banker']",
            ]
            
            self.logger.info(f"Banker 베팅 영역 찾는 중...")
            for selector in banker_selectors:
                try:
                    elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and elements[0].is_displayed():
                        self.logger.info(f"Banker 베팅 영역 찾음: {selector}")
                        return elements[0]
                except Exception as e:
                    self.logger.debug(f"선택자 '{selector}' 실패: {e}")
                    continue
            
            # XPath로 시도 (Banker용) - 후순위
            xpath_expressions = [
                "//div[contains(@class, 'banker--') and contains(@class, 'content--')]",
                "//div[contains(@data-betspot-destination, 'Banker')]"
            ]
            
            for xpath in xpath_expressions:
                try:
                    elements = self.devtools.driver.find_elements(By.XPATH, xpath)
                    if elements and elements[0].is_displayed():
                        self.logger.info(f"Banker 베팅 영역 찾음 (XPath): {xpath}")
                        return elements[0]
                except Exception as e:
                    self.logger.debug(f"XPath '{xpath}' 실패: {e}")
                    continue
        
        # 최후의 수단... (기존 코드 유지)
        self.logger.info(f"기본 방법으로 {bet_type} 베팅 영역을 찾지 못함. 고급 검색 시도...")
        try:
            from utils.iframe_utils import find_element_in_iframes
            
            # 베팅 타입에 따른 고급 검색
            if bet_type == 'P':
                advanced_selectors = [
                    "div[class*='player']",
                    "div[class*='content'][class*='player']"
                ]
            else:  # bet_type == 'B'
                advanced_selectors = [
                    "div[class*='banker']", 
                    "div[class*='content'][class*='banker']"
                ]
            
            for selector in advanced_selectors:
                success, element = find_element_in_iframes(
                    self.devtools.driver,
                    By.CSS_SELECTOR, 
                    selector,
                    max_depth=3
                )
                
                if success:
                    self.logger.info(f"고급 검색으로 {bet_type} 베팅 영역 찾음: {selector}")
                    return element
                    
        except Exception as e:
            self.logger.warning(f"고급 검색 중 오류: {e}")
        
        self.logger.error(f"{bet_type} 베팅 영역을 찾을 수 없습니다.")
        return None


    def _check_betting_label(self):
        """
        베팅 레이블 확인 ("총 베팅금" 또는 "지난 우승")
        
        Returns:
            str: 레이블 텍스트 또는 None
        """
        try:
            # 정확한 데이터 속성으로 레이블 요소 찾기
            label_element = self.devtools.driver.find_element(
                By.CSS_SELECTOR, 
                "span[data-role='total-bet-label-title']"
            )
            
            if label_element:
                return label_element.text.strip()
            return None
        except Exception as e:
            self.logger.debug(f"베팅 레이블 확인 실패: {e}")
            return None
        

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
        
        # 마틴 단계 확인 및 동기화 - 오류 수정
        martin_step = 0
        martin_step = get_widget_position(self.main_window)

        # 마틴 서비스 동기화
        if hasattr(self.main_window, 'trading_manager'):
            self.main_window.trading_manager.martin_service.current_step = martin_step

        self.logger.info(f"베팅 위젯 위치 카운터를 마틴 단계와 동기화: 포지션={martin_step+1}")
        
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
                
                # 타이 직후 플래그 추가
                self.main_window.trading_manager.had_tie_last_round = True
                self.logger.info(f"타이(T) 결과로 베팅 상태 초기화 및 타이 직후 플래그 설정")
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
    
    def _wait_for_active_chips(self, max_wait=60, interval=1):
        """
        최대 max_wait초 동안 interval초 간격으로 활성화 칩을 기다림.
        활성화된 칩 리스트를 반환. 없으면 빈 리스트 반환.
        """
        waited = 0
        while waited < max_wait:
            available_chips = [chip for chip in self._get_available_chip_values() if chip > 0]
            if available_chips:
                return available_chips
            self.logger.info(f"활성화된 칩이 없음. {interval}초 후 재시도... (누적 대기: {waited+interval}s)")
            time.sleep(interval)
            waited += interval
        self.logger.error("최대 대기 시간 동안 활성화된 칩을 찾지 못했습니다.")
        return []

    def _remove_failed_room(self, room_id: str):
        """실패한 방을 목록에서 제거"""
        self.target_streak_rooms = [room for room in self.target_streak_rooms if room['room_id'] != room_id]
        self.logger.info(f"방 {room_id} 제거 완료")