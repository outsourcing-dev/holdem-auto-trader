# services/betting_service.py - 베팅 접수와 결과 확인 분리된 버전
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
from utils.common_iframe import IframeNavigator

class BettingService:
    def __init__(self, devtools, main_window, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        self.devtools = devtools
        self.main_window = main_window
        
        # iframe 네비게이터 초기화 (안전한 초기화)
        try:
            self.iframe_navigator = IframeNavigator(devtools.driver, self.logger)
        except Exception as e:
            self.logger.error(f"IframeNavigator 초기화 실패: {e}")
            self.iframe_navigator = None
        
        # 베팅 상태 관리
        self.has_bet_current_round = False
        self.current_bet_round = 0
        self.last_bet_type = None
        self.last_bet_time = 0
        
        self.pending_bet = None  # 결과 대기 중인 베팅 정보
        self.bet_result_confirmed = False
        self.last_bet_result = None
        
        # 🔥 중복 베팅 방지
        self.is_betting_in_progress = False  # 베팅 진행 중 플래그
        self.last_bet_timestamp = 0  # 마지막 베팅 시간

    # services/betting_service.py - 수정 부분

    def place_bet(self, bet_type, current_room_name, game_count, is_trading_active, bet_amount=None):
        """베팅 실행 - 접수 확인에만 집중, 결과는 나중에 확인"""
        self.logger.info(f"🎯 베팅 시도 - 타입: {bet_type}, 게임: {game_count}, 금액: {bet_amount}")
        self.logger.info(f"🏠 방: {current_room_name}, 거래활성: {is_trading_active}")

        try:
            self.logger.info("🔍 베팅 조건 검증 시작...")
            if not self._validate_bet_conditions(bet_type, is_trading_active):
                self.logger.warning("❌ 베팅 조건 검증 실패")
                return False
            
            self.logger.info("✅ 베팅 조건 검증 통과")
            
            # 현재 라운드에 대한 베팅 상태 확인 및 업데이트
            self.check_is_bet_for_current_round(game_count)
            
            gc.collect()

            # IframeNavigator를 사용한 iframe 전환 (fallback 포함)
            iframe_success = False
            
            if self.iframe_navigator:
                # 메인 iframe 전환 시도
                if self.iframe_navigator.switch_to_game_iframe():
                    iframe_success = True
                else:
                    # 중첩 iframe 시도
                    if self.iframe_navigator.switch_to_nested_iframe("iframe", "iframe"):
                        iframe_success = True
            
            # IframeNavigator 실패 시 기존 방식으로 fallback
            if not iframe_success:
                self.logger.warning("IframeNavigator 실패, 기존 방식으로 시도")
                if not switch_to_iframe_with_retry(self.devtools.driver, max_retries=3, max_depth=2):
                    self.logger.error("베팅: 모든 iframe 전환 실패, 베팅 진행 불가")
                    return False

            # 베팅 가능한 상태까지 대기
            if not self._wait_for_betting_available():
                self.logger.warning("베팅 가능 상태 대기 실패")
                return False

            # 🔥 최적화된 로직: 베팅 가능 상태 즉시 → iframe 파싱 → 서버 요청 → 베팅 실행
            start_time = time.time()
            
            # 1단계: 베팅 가능 상태에서 즉시 iframe에서 15개 결과 추출
            latest_round_number, latest_results = self._extract_latest_results_fast()
            
            if latest_round_number is None or not latest_results:
                self.logger.warning("빠른 결과 추출 실패 - 기존 정보 사용")
                latest_round_number = game_count
                latest_results = []
            else:
                if latest_round_number != game_count:
                    self.logger.info(f"⚡ 라운드 업데이트: {game_count} → {latest_round_number}")
            
            # 2단계: 서버에 빠른 예측값 요청 (결과가 충분한 경우만)
            if len(latest_results) >= 5:
                room_id = getattr(self.main_window.trading_manager.current_target_room, 'room_id', None) if hasattr(self.main_window.trading_manager, 'current_target_room') else None
                if room_id and hasattr(self.main_window.trading_manager, 'server_client'):
                    new_prediction = self.main_window.trading_manager.server_client.get_next_prediction(room_id, latest_results)
                    if new_prediction and new_prediction in ['P', 'B'] and new_prediction != bet_type:
                        self.logger.info(f"⚡ 예측값 업데이트: {bet_type} → {new_prediction}")
                        bet_type = new_prediction
            
            elapsed = time.time() - start_time
            self.logger.info(f"⚡ 베팅 전 처리 완료: {elapsed:.3f}초 (라운드: {latest_round_number}, 결과: {len(latest_results)}개)")
            
            # 위젯 마커 초기화 로직
            if hasattr(self.main_window, 'betting_widget'):
                marker = getattr(self.main_window.betting_widget, 'get_current_marker', lambda: None)()
                if marker == "O":
                    self.logger.info("베팅 직전: 위젯 마커 'O' 감지 → 마커 초기화")
                    self.main_window.betting_widget.reset_step_markers()
                    self.main_window.betting_widget.room_position_counter = 0

            # 타이 직후 처리 로직
            had_tie_last_round = getattr(self.main_window.trading_manager, 'had_tie_last_round', False)
            if had_tie_last_round:
                self.logger.info("타이 직후 베팅: 동일 위치 유지")
                self.main_window.trading_manager.had_tie_last_round = False

            # 🔥 베팅 실행 (접수 확인만)
            bet_success = self._execute_betting_placement(bet_type, bet_amount)

            if bet_success:
                # 🔥 베팅 결과 추적 시작 (최신 라운드 번호 사용)
                actual_bet_round = latest_round_number + 1  # 실제 베팅 적용 라운드
                
                # 기존 pending_bet 시스템
                self._start_result_tracking(bet_type, latest_round_number, bet_amount, current_room_name)
                
                # 🔥 새로운 BettingResultTracker도 시작 (게임 프로세서용)
                if hasattr(self.main_window, 'trading_manager') and hasattr(self.main_window.trading_manager, 'game_processor'):
                    if hasattr(self.main_window.trading_manager.game_processor, 'betting_tracker'):
                        betting_tracker = self.main_window.trading_manager.game_processor.betting_tracker
                        if not betting_tracker.is_waiting_for_result():
                            betting_tracker.start_betting_tracking(
                                bet_type=bet_type,
                                round_number=actual_bet_round,  # 실제 베팅 적용 라운드
                                bet_amount=bet_amount,
                                room_name=current_room_name
                            )
                            self.logger.info(f"🎯 [BettingService] 베팅 추적 시작:")
                            self.logger.info(f"  - 베팅 타입: {bet_type}")
                            self.logger.info(f"  - 적용 라운드: {actual_bet_round}")
                            self.logger.info(f"  - 베팅 금액: {bet_amount:,}원")
                            self.logger.info(f"  - 방 이름: {current_room_name}")
                        else:
                            self.logger.warning("⚠️ 이미 베팅 결과 대기 중 - 추적 시작 건너뜀")
                
                self._handle_successful_bet(bet_type, latest_round_number, current_room_name)
                self.has_bet_current_round = True
                return True
            else:
                self.logger.error(f"❌ 베팅 실패 - 다음 라운드를 기다립니다")
                # 베팅 실패 시 상태 초기화
                self.has_bet_current_round = False
                return False

        except Exception as e:
            self.logger.error(f"베팅 중 오류 발생: {e}", exc_info=True)
            return False

    def _execute_betting_placement(self, bet_type, bet_amount=None):
        """베팅 접수 실행 - 칩을 베팅 영역에 올리는 것에만 집중"""
        bet_element = self._find_betting_area(bet_type)
        if not bet_element:
            self.logger.error(f"{bet_type} 베팅 영역을 찾을 수 없음")
            return False

        self.logger.info(f"베팅 접수 시작: {bet_type}, 금액: {bet_amount:,}원")

        # 동적으로 사용 가능한 칩 값들 가져오기
        available_chips = self._wait_for_active_chips(max_wait=60, interval=1)
        if not available_chips:
            self.logger.error("사용 가능한 칩이 없습니다. 베팅을 중단합니다.")
            return False

        # 베팅 금액에 따른 칩 조합 계산
        chip_clicks = self._calculate_chip_combination(bet_amount, available_chips)
        if not chip_clicks:
            self.logger.error("칩 조합 계산 실패")
            return False

        self.logger.info(f"베팅 금액 {bet_amount:,}원 -> 칩별 클릭 횟수: {chip_clicks}")

        # 실제 칩 배치
        placement_success = self._place_chips_on_area(chip_clicks, bet_element, bet_type)
        
        if placement_success:
            # 🔥 베팅 접수 확인 (충분한 대기 + 다양한 확인 방법)
            return self._verify_betting_placement(bet_amount, bet_type)
        
        return False

    def _calculate_chip_combination(self, bet_amount, available_chips):
        """칩 조합 계산"""
        chip_clicks = {}
        remaining = bet_amount

        for chip in sorted(available_chips, reverse=True):  # 큰 칩부터
            count = remaining // chip
            if count > 0:
                chip_clicks[chip] = count
                remaining %= chip

        # 칩 조합이 없으면 가장 작은 칩으로 기본 베팅
        if not chip_clicks and available_chips:
            smallest_chip = min(available_chips)
            chip_clicks[smallest_chip] = 1
            self.logger.warning(f"정확한 금액 불가, {smallest_chip}원 칩으로 기본 베팅")

        return chip_clicks

    def _place_chips_on_area(self, chip_clicks, bet_element, bet_type):
        """실제 칩을 베팅 영역에 배치"""
        bet_successful = False
        
        for chip_value, clicks in chip_clicks.items():
            # 칩 선택
            chip_element = self._find_chip(chip_value)
            if not chip_element:
                self.logger.warning(f"{chip_value}원 칩을 찾지 못함")
                continue

            # 칩 클릭 (선택)
            try:
                self._safe_click(chip_element, f"{chip_value}원 칩")
                # 짧은 대기는 더 효율적인 대기로 교체
                self.iframe_navigator.wait_for_element(By.TAG_NAME, "body", timeout=0.2)
            except Exception as e:
                self.logger.error(f"{chip_value}원 칩 클릭 실패: {e}")
                continue

            # 베팅 영역에 칩 배치 (지정된 횟수만큼)
            for i in range(clicks):
                try:
                    self._safe_click(bet_element, f"{bet_type} 베팅 영역")
                    time.sleep(0.1)
                    bet_successful = True
                except Exception as e:
                    self.logger.error(f"베팅 영역 클릭 실패 (시도 {i+1}): {e}")
                    continue

        return bet_successful

    def _verify_betting_placement(self, expected_amount, bet_type, max_attempts=5):
        """베팅이 정상적으로 접수되었는지 확인 - 🔥 개선된 버전"""
        self.logger.info(f"베팅 접수 확인 시작 (기대 금액: {expected_amount:,}원)")
        
        for attempt in range(max_attempts):
            try:
                # 베팅 처리 대기
                WebDriverWait(self.devtools.driver, 1).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                
                # 방법 1: 베팅 금액 확인
                current_amount = self._get_current_bet_amount()
                if current_amount > 0:
                    # 🔥 오차 허용 범위 확대
                    amount_diff = abs(current_amount - expected_amount)
                    if amount_diff <= max(1000, expected_amount * 0.1):  # 1000원 또는 10% 오차 허용
                        self.logger.info(f"✅ 베팅 접수 확인 - 금액 일치: {current_amount:,}원 (오차: {amount_diff}원)")
                        return True
                
                # 방법 2: 레이블 확인 (보조적)
                current_label = self._check_betting_label()
                if current_label == "총 베팅금":
                    self.logger.info(f"✅ 베팅 접수 확인 - 레이블: {current_label}")
                    return True
                
                # 방법 3: 베팅 영역에 칩이 올라갔는지 시각적 확인
                if self._check_chips_on_betting_area(bet_type):
                    self.logger.info(f"✅ 베팅 접수 확인 - {bet_type} 영역에 칩 확인")
                    return True
                
                # 🔥 방법 4: 금액이 0보다 크면 일단 성공으로 간주 (관대한 판단)
                if current_amount > 0:
                    self.logger.info(f"✅ 베팅 접수 확인 - 베팅 금액 존재: {current_amount:,}원 (관대한 판단)")
                    return True
                    
                self.logger.debug(f"베팅 확인 시도 {attempt+1}: 금액={current_amount}, 레이블={current_label}")
                
            except Exception as e:
                self.logger.warning(f"베팅 확인 시도 {attempt+1} 실패: {e}")
                continue
        
        self.logger.error("🔥 베팅 접수 확인 실패 - 모든 방법 시도됨")
        return False

    def _check_chips_on_betting_area(self, bet_type):
        """베팅 영역에 칩이 올라갔는지 시각적 확인"""
        try:
            # 베팅 영역 다시 찾기
            bet_area = self._find_betting_area(bet_type)
            if not bet_area:
                return False
            
            # 베팅 영역 내부에 칩 요소가 있는지 확인
            chip_selectors = [
                ".chip", ".betting-chip", "[class*='chip']", 
                ".token", "[class*='token']", "[class*='bet']"
            ]
            
            for selector in chip_selectors:
                try:
                    chips = bet_area.find_elements(By.CSS_SELECTOR, selector)
                    if chips:
                        self.logger.debug(f"베팅 영역에서 칩 발견: {len(chips)}개")
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.debug(f"칩 시각 확인 오류: {e}")
            return False

    # services/betting_service.py - _start_result_tracking 메서드 수정

    def _start_result_tracking(self, bet_type, round_number, bet_amount, room_name):
        """베팅 결과 추적 시작 (게임 결과 대기)"""
        # 🔥 올바른 로직: 표시된 라운드는 완료된 라운드, 베팅은 다음 라운드에 적용됨
        actual_bet_round = round_number + 1
        
        self.pending_bet = {
            'type': bet_type,
            'round': actual_bet_round,  # 🔥 다음 라운드로 설정 (베팅 대상)
            'amount': bet_amount,
            'room_name': room_name,
            'timestamp': time.time()
        }
        self.bet_result_confirmed = False
        self.last_bet_result = None
        
        self.logger.info(f"🎯 베팅 결과 추적 시작: {bet_type} → 라운드 {actual_bet_round} (금액: {bet_amount:,}원)")
        self.logger.info(f"📍 iframe 표시: {round_number}번째 결과 완료, 베팅 적용: {actual_bet_round}번째 게임")

    def check_pending_bet_result(self, current_round, game_result):
        """🔥 대기 중인 베팅의 결과 확인 - 핵심 메서드"""
        if not self.pending_bet or self.bet_result_confirmed:
            return None
        
        bet_round = self.pending_bet['round']
        
        # 🔥 디버깅 로그 추가
        self.logger.debug(f"📊 베팅 결과 확인: 베팅라운드={bet_round}, 현재라운드={current_round}, 결과={game_result}")
        
        # 베팅한 라운드의 결과인지 확인 (정확히 일치해야 함)
        if current_round != bet_round:
            if current_round < bet_round:
                self.logger.debug(f"⏳ 아직 베팅 라운드 도달 안함: 현재={current_round}, 베팅={bet_round}")
            else:
                self.logger.warning(f"⚠️ 베팅 라운드를 놓침: 현재={current_round}, 베팅={bet_round}")
            return None
        
        bet_type = self.pending_bet['type']
        
        # 🔥 결과 판정
        if game_result == 'T':
            result_status = "tie"
            result_text = "무승부"
            marker = "T"
        elif bet_type == game_result:
            result_status = "win"
            result_text = "적중"
            marker = "O"
        else:
            result_status = "lose"
            result_text = "실패"  
            marker = "X"
        
        # 결과 확정
        self.bet_result_confirmed = True
        self.last_bet_result = result_status
        
        self.logger.info(f"🎲 베팅 결과 확정: {bet_type} vs {game_result} = {result_text}")
        self.logger.info(f"✅ {current_round}번째 게임 결과 매칭 완료")
        
        # UI 업데이트
        if hasattr(self.main_window, 'betting_widget'):
            widget_pos = get_widget_position(self.main_window)
            self.main_window.betting_widget.set_step_marker(widget_pos, marker)
        
        # 베팅 정보 초기화 (무승부가 아닌 경우)
        if result_status != "tie":
            self.pending_bet = None
            self.has_bet_current_round = False
        
        return {
            'status': result_status,
            'bet_type': bet_type,
            'game_result': game_result,
            'result_text': result_text,
            'bet_round': bet_round,
            'current_round': current_round
        }

    def get_pending_bet_info(self):
        """현재 대기 중인 베팅 정보 반환"""
        if self.pending_bet:
            return {
                'type': self.pending_bet['type'],
                'round': self.pending_bet['round'], 
                'amount': self.pending_bet['amount'],
                'waiting_time': time.time() - self.pending_bet['timestamp']
            }
        return None

    def _safe_click(self, element, element_name=""):
        """안전한 클릭 - 여러 방법 시도"""
        try:
            # 방법 1: 일반 클릭
            element.click()
            self.logger.debug(f"일반 클릭 성공: {element_name}")
            return True
        except Exception as e1:
            try:
                # 방법 2: JavaScript 클릭  
                self.devtools.driver.execute_script("arguments[0].click();", element)
                self.logger.debug(f"JS 클릭 성공: {element_name}")
                return True
            except Exception as e2:
                try:
                    # 방법 3: ActionChains 클릭
                    ActionChains(self.devtools.driver).click(element).perform()
                    self.logger.debug(f"ActionChains 클릭 성공: {element_name}")
                    return True
                except Exception as e3:
                    self.logger.error(f"모든 클릭 방법 실패 {element_name}: {e1}, {e2}, {e3}")
                    return False

    # 기존 메서드들 유지 (길어서 핵심만 포함)
    def _validate_bet_conditions(self, bet_type, is_trading_active):
        """베팅 전 조건 검증"""
        if hasattr(self, 'last_bet_time'):
            elapsed = time.time() - self.last_bet_time
            if elapsed < 3.0:  # 5초 → 3초로 완화
                self.logger.warning(f"마지막 배팅 후 {elapsed:.1f}초밖에 지나지 않았습니다. 최소 3초 대기 필요.")
                return False
        
        if not is_trading_active:
            self.logger.info("자동 매매가 활성화되지 않았습니다.")
            return False
        
        if self.has_bet_current_round:
            self.logger.info(f"이미 현재 라운드에 베팅했습니다. (라운드: {self.current_bet_round})")
            return False
        
        if bet_type not in ['P', 'B']:
            self.logger.error(f"잘못된 베팅 타입: {bet_type}. 'P' 또는 'B'만 가능합니다.")
            return False
            
        return True

    def _wait_for_betting_available(self):
        """베팅 가능 상태가 될 때까지 대기"""
        self.logger.info("베팅 가능 상태 확인 시작...")
        max_attempts = 60
        
        for attempt in range(max_attempts):
            try:
                if self._check_chips_active():
                    self.logger.info("✅ 활성화된 칩 발견 - 베팅 가능 상태")
                    
                    if self._check_betting_areas_active():
                        self.logger.info("✅ 베팅 영역도 활성화됨 - 베팅 준비 완료")
                        return True
                    else:
                        self.logger.info("⏳ 베팅 영역 활성화 대기 중...")
                else:
                    self.logger.debug(f"⏳ 칩 비활성화 상태 - 대기 중... ({attempt+1}/{max_attempts})")
                
                time.sleep(1)
            except Exception as e:
                self.logger.warning(f"베팅 가능 상태 확인 중 오류: {e}")
                time.sleep(0.5)
        
        self.logger.warning("베팅 가능 상태 대기 시간 초과.")
        return False

    def _check_chips_active(self):
        """칩 활성화 상태 확인"""
        try:
            chip_selectors = [
                "div.chip--29b81[data-role='chip']",
                "div[data-role='chip']",
                "div.chip[data-value]"
            ]
            
            for selector in chip_selectors:
                chip_elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for chip_element in chip_elements:
                    if chip_element.is_displayed():
                        chip_class = chip_element.get_attribute("class") or ""
                        if "disabled" not in chip_class.lower():
                            chip_value = chip_element.get_attribute("data-value")
                            self.logger.debug(f"활성화된 칩 발견: {chip_value}원")
                            return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"칩 활성화 확인 중 오류: {e}")
            return False

    def _check_betting_areas_active(self):
        """베팅 영역 활성화 상태 확인"""
        try:
            player_selectors = [
                "div.spot--5ad7f[data-betspot-destination='Player']",
                "div.content--e4fdb.player--2c620",
                "div.player--2c620"
            ]
            
            banker_selectors = [
                "div.spot--5ad7f[data-betspot-destination='Banker']",
                "div.content--e4fdb.banker--6b486", 
                "div.banker--6b486"
            ]
            
            # Player 영역 활성화 확인
            for selector in player_selectors:
                try:
                    elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and elements[0].is_displayed():
                        element_class = elements[0].get_attribute("class") or ""
                        if "disabled" not in element_class.lower():
                            self.logger.debug("Player 베팅 영역 활성화됨")
                            break
                except:
                    continue
            else:
                return False
            
            # Banker 영역 활성화 확인
            for selector in banker_selectors:
                try:
                    elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and elements[0].is_displayed():
                        element_class = elements[0].get_attribute("class") or ""
                        if "disabled" not in element_class.lower():
                            self.logger.debug("Banker 베팅 영역 활성화됨")
                            return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.warning(f"베팅 영역 활성화 확인 중 오류: {e}")
            return False

    def _find_chip(self, chip_value):
        """칩 찾기"""
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
                        chip_class = element.get_attribute("class") or ""
                        is_disabled = element.get_attribute("disabled")
                        
                        if "disabled" not in chip_class.lower() and not is_disabled:
                            return element
            except:
                continue
        
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
                "div.chip[data-value]",
                # 추가 선택자
                "div[class*='chip'][data-value]",
                "div.chipStack[data-value]",
                "div[class*='chipStack'][data-value]"
            ]
            
            available_chips = []
            
            for selector in chip_selectors:
                chip_elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                
                if chip_elements:
                    self.logger.debug(f"선택자 {selector}로 {len(chip_elements)}개 칩 발견")
                
                for chip_element in chip_elements:
                    if chip_element.is_displayed():
                        chip_class = chip_element.get_attribute("class") or ""
                        chip_value = chip_element.get_attribute("data-value")
                        
                        # 디버깅 로그
                        self.logger.debug(f"칩 정보 - 클래스: {chip_class}, 값: {chip_value}")
                        
                        if "disabled" not in chip_class.lower() and chip_value:
                            try:
                                value = int(chip_value)
                                if value > 0:  # 0보다 큰 값만 추가
                                    available_chips.append(value)
                            except ValueError:
                                continue
            
            available_chips = sorted(list(set(available_chips)), reverse=True)
            self.logger.info(f"사용 가능한 칩 값들: {available_chips}")
            
            # 칩이 없으면 게임 진행 중 (베팅 불가)
            if not available_chips:
                self.logger.warning("활성화된 칩을 찾을 수 없음 - 게임이 이미 진행 중 (베팅 불가)")
                return []  # 빈 리스트 반환
                
            return available_chips
            
        except Exception as e:
            self.logger.warning(f"사용 가능한 칩 값 조회 실패: {e}")
            return [10000, 5000, 1000]  # 기본 칩 값

    def _find_betting_area(self, bet_type):
        """베팅 영역 찾기"""
        if bet_type == 'P':
            player_selectors = [
                "div.spot--5ad7f[data-betspot-destination='Player']",
                "div.content--e4fdb.player--2c620",
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
                    
        elif bet_type == 'B':
            banker_selectors = [
                "div.spot--5ad7f[data-betspot-destination='Banker']",
                "div.content--e4fdb.banker--6b486",
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
        
        self.logger.error(f"{bet_type} 베팅 영역을 찾을 수 없습니다.")
        return None

    def _check_betting_label(self):
        """베팅 레이블 확인 ("총 베팅금" 또는 "지난 우승")"""
        try:
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
                    return int(''.join(filter(str.isdigit, amount_text)) or '0')
            
            return 0
        except Exception as e:
            self.logger.warning(f"베팅 금액 확인 실패: {e}")
            return 0

    def _handle_successful_bet(self, bet_type, game_count, current_room_name):
        """성공한 베팅 처리"""
        self.has_bet_current_round = True
        # 현재 표시된 라운드는 완료된 라운드, 실제 베팅은 다음 라운드에 적용
        self.current_bet_round = game_count + 1  # 실제 베팅이 적용되는 라운드
        self.last_bet_type = bet_type
        self.last_bet_time = time.time()
        
        # 🔥 올바른 로직: 표시된 라운드는 완료된 라운드, 베팅은 다음 라운드에 적용됨       
        actual_bet_round = game_count + 1
        self.logger.info(f"[베팅완료] 표시된 완료 라운드: {game_count}, 베팅타입: {bet_type}")
        self.logger.info(f"📍 실제 베팅 적용 라운드: {actual_bet_round}")
        self.logger.info(f"⏳ 라운드 {actual_bet_round}의 결과를 대기합니다")
        
        display_room_name = current_room_name.split('\n')[0] if '\n' in current_room_name else current_room_name
        
        martin_step = 0
        martin_step = get_widget_position(self.main_window)

        if hasattr(self.main_window, 'trading_manager'):
            self.main_window.trading_manager.martin_service.current_step = martin_step

        self.logger.info(f"베팅 위젯 위치 카운터를 마틴 단계와 동기화: 포지션={martin_step+1}")
        
        self.main_window.update_betting_status(
            room_name=f"{display_room_name}",
            pick=bet_type
        )
        
        # 🔥 베팅 후 대기 상태 설정
        if hasattr(self.main_window, 'trading_manager'):
            self.main_window.trading_manager._is_waiting_for_next_game = True
            self.logger.info(f"⏳ 게임 결과 대기 모드 설정 (라운드 {actual_bet_round})")
            
    def _wait_for_active_chips(self, max_wait=60, interval=1):
        """활성화된 칩이 나타날 때까지 대기"""
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

    def reset_betting_state(self, new_round=None):
        """베팅 상태 초기화"""
        previous_round = self.current_bet_round
        self.has_bet_current_round = False
        self.current_bet_round = new_round if new_round is not None else 0
        self.bet_result_confirmed = False
        self.last_bet_result = None
        # 🔥 대기 중인 베팅 정보는 유지 (게임 결과를 기다리고 있을 수 있음)

    def check_is_bet_for_current_round(self, current_round):
        """현재 라운드에 베팅했는지 확인"""
        # 새로운 라운드가 시작되었는지 확인
        if current_round > self.current_bet_round:
            # 새 라운드 시작 - 베팅 상태 초기화
            self.logger.info(f"새 라운드({current_round}) 감지, 이전 베팅 기록({self.current_bet_round}) 초기화")
            self.has_bet_current_round = False
            self.current_bet_round = current_round
            return False
            
        # 현재 라운드에 이미 베팅했는지 확인
        return self.has_bet_current_round and self.current_bet_round == current_round

    def check_betting_result(self, bet_type, latest_result, current_room_name, result_count, step=None):
        """🔥 기존 베팅 결과 확인 (호환성 유지)"""
        try:
            if step is None:
                step = self.main_window.trading_manager.martin_service.current_step + 1

            result_count += 1
            
            if latest_result == 'T':
                self.logger.info(f"게임 결과: 타이(T) - 무승부 처리")
                result_text = "무승부"
                result_status = "tie"
                marker = "T"
                
                self.has_bet_current_round = False
                self.main_window.trading_manager.had_tie_last_round = True
                self.logger.info(f"타이(T) 결과로 베팅 상태 초기화 및 타이 직후 플래그 설정")
            else:
                if bet_type == latest_result:
                    result_status = "win"
                    result_text = "적중"
                    marker = "O"
                else:
                    result_status = "lose"
                    result_text = "실패"
                    marker = "X"
                self.logger.info(f"베팅 결과 확인 - 베팅: {bet_type}, 결과: {latest_result}, 승패: {result_text}, 단계: {step}")
            
            self.main_window.add_betting_result(
                no=result_count,
                room_name=current_room_name,
                step=step,
                result=result_text
            )
            
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

    def has_pending_bet(self):
        """🔥 대기 중인 베팅이 있는지 확인"""
        return self.pending_bet is not None and not self.bet_result_confirmed

    def get_pending_bet_status(self):
        """🔥 대기 중인 베팅 상태 반환"""
        if self.pending_bet:
            waiting_time = time.time() - self.pending_bet['timestamp']
            return {
                'has_pending': True,
                'bet_type': self.pending_bet['type'],
                'bet_round': self.pending_bet['round'],
                'bet_amount': self.pending_bet['amount'],
                'waiting_time': waiting_time,
                'result_confirmed': self.bet_result_confirmed
            }
        return {
            'has_pending': False,
            'bet_type': None,
            'bet_round': None,
            'bet_amount': None,
            'waiting_time': 0,
            'result_confirmed': False
        }

    def clear_pending_bet(self):
        """🔥 대기 중인 베팅 정보 초기화"""
        self.pending_bet = None
        self.bet_result_confirmed = False
        self.last_bet_result = None
        self.is_betting_in_progress = False
        self.logger.info("대기 중인 베팅 정보 초기화됨")
        
    def reset_betting_state(self, new_round=None):
        """베팅 상태 초기화 - 강화"""
        previous_round = self.current_bet_round
        self.has_bet_current_round = False
        self.current_bet_round = new_round if new_round is not None else 0
        self.is_betting_in_progress = False  # 🔥 추가

    def _extract_latest_results_fast(self):
        """⚡ 베팅 가능 상태에서 즉시 iframe에서 최신 결과 추출 (속도 최적화)"""
        try:
            start_time = time.time()
            
            # 이미 iframe 상태이므로 별도 전환 불필요
            # 1. 라운드 번호 빠른 추출
            round_number = self._find_round_number_fast()
            
            # 2. P,B 결과 빠른 추출 (15개)
            results = self._find_game_results_fast(15)
            
            elapsed = time.time() - start_time
            self.logger.info(f"⚡ iframe 빠른 추출: {elapsed:.3f}초 (라운드: {round_number}, 결과: {len(results)}개)")
            
            return round_number, results
            
        except Exception as e:
            self.logger.error(f"빠른 결과 추출 오류: {e}")
            return None, []

    def _find_round_number_fast(self):
        """⚡ 라운드 번호 빠른 추출"""
        try:
            # 우선순위 1: data-role="gameCount" 직접 찾기
            try:
                game_count_element = self.devtools.driver.find_element(
                    By.CSS_SELECTOR, 
                    'div[data-role="gameCount"]'
                )
                if game_count_element:
                    text = game_count_element.text.strip()
                    if text.isdigit():
                        return int(text)
            except:
                pass
            
            # 우선순위 2: JavaScript로 빠른 찾기
            try:
                js_script = """
                var gameCountEl = document.querySelector('[data-role="gameCount"]');
                if (gameCountEl && gameCountEl.textContent.trim()) {
                    var num = parseInt(gameCountEl.textContent.trim());
                    if (num >= 1 && num <= 200) return num;
                }
                return 0;
                """
                result = self.devtools.driver.execute_script(js_script)
                if result and result > 0:
                    return result
            except:
                pass
            
            return 0
            
        except Exception as e:
            self.logger.debug(f"빠른 라운드 번호 찾기 오류: {e}")
            return 0

    def _find_game_results_fast(self, max_count=15):
        """⚡ P,B 게임 결과 빠른 추출 (Bead Road SVG 최적화)"""
        try:
            # JavaScript를 이용한 빠른 SVG 데이터 추출
            js_script = f"""
            try {{
                var results = [];
                var coordinates = {{}};
                
                // Bead Road SVG coordinates 요소들 찾기
                var svgElements = document.querySelectorAll('svg[data-role="Bead-road"] svg[data-type="coordinates"]');
                
                for (var i = 0; i < svgElements.length && results.length < {max_count + 10}; i++) {{
                    var svg = svgElements[i];
                    var x = parseInt(svg.getAttribute('data-x'));
                    var y = parseInt(svg.getAttribute('data-y'));
                    
                    if (isNaN(x) || isNaN(y)) continue;
                    
                    var result = null;
                    
                    // 방법 1: text 요소에서 직접 가져오기
                    var textEl = svg.querySelector('text');
                    if (textEl && textEl.textContent.trim()) {{
                        var text = textEl.textContent.trim().toUpperCase();
                        if (text === 'P' || text === 'B' || text === 'T') {{
                            result = text;
                        }}
                    }}
                    
                    // 방법 2: roadItem name 속성
                    if (!result) {{
                        var roadItem = svg.querySelector('svg[data-type="roadItem"]');
                        if (roadItem) {{
                            var name = roadItem.getAttribute('name');
                            if (name) {{
                                if (name.includes('Player')) result = 'P';
                                else if (name.includes('Banker')) result = 'B';
                                else if (name.includes('Tie')) result = 'T';
                            }}
                        }}
                    }}
                    
                    if (result) {{
                        coordinates[x + '_' + y] = {{x: x, y: y, result: result}};
                    }}
                }}
                
                // 좌표 정렬 후 P,B만 필터링
                var sortedCoords = Object.values(coordinates).sort((a, b) => {{
                    if (a.x !== b.x) return a.x - b.x;
                    return a.y - b.y;
                }});
                
                var pbResults = [];
                for (var i = 0; i < sortedCoords.length; i++) {{
                    if (sortedCoords[i].result === 'P' || sortedCoords[i].result === 'B') {{
                        pbResults.push(sortedCoords[i].result);
                    }}
                }}
                
                return pbResults.slice(-{max_count}); // 최근 N개만
                
            }} catch (e) {{
                return [];
            }}
            """
            
            results = self.devtools.driver.execute_script(js_script)
            
            if results and isinstance(results, list):
                pb_results = [r for r in results if r in ['P', 'B']]
                self.logger.debug(f"⚡ JS 빠른 추출: {len(pb_results)}개 P,B 결과")
                return pb_results
            else:
                self.logger.debug("JS 빠른 추출 실패 - 빈 결과")
                return []
                
        except Exception as e:
            self.logger.debug(f"빠른 게임 결과 추출 오류: {e}")
            return []