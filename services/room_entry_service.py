import random
import time
import logging
import re
from PyQt6.QtWidgets import QMessageBox
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.iframe_utils import IframeManager, switch_to_iframe_with_retry
from utils.unified_server_client import get_server_client

class RoomEntryService:
    def __init__(self, devtools, main_window, room_manager, logger=None):
        """
        방 입장 서비스 초기화
        
        Args:
            devtools (DevToolsController): 브라우저 제어 객체
            main_window (QMainWindow): 메인 윈도우 객체
            room_manager (RoomManager): 방 관리 객체 (레거시 호환용)
            logger (logging.Logger, optional): 로깅을 위한 로거 객체
        """
        # 로거 설정
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # 의존성 주입
        self.devtools = devtools
        self.main_window = main_window
        self.room_manager = room_manager  # 레거시 호환용 유지
        
        # 서버 클라이언트 초기화
        self.server_client = get_server_client()
        
        # iframe 매니저 초기화
        self.iframe_manager = None
        
        # 새로고침 관련 상태 변수
        self.last_refresh_time = 0
        self.refresh_interval = 60  # 새로고침 사이의 최소 간격(초)
        self.consecutive_failures = 0
        
        # 서버 기반 상태 변수
        self.current_monitoring_session = None
        self.last_streak_room_request = 0
        self.streak_room_request_interval = 30  # 연패 방 요청 간격(초)

    def enter_specific_room(self, room_name, max_retries=3):
        """
        서버에서 추천받은 특정 방에 직접 입장
        
        Args:
            room_name (str): 입장할 방 이름
            max_retries (int): 최대 재시도 횟수
            
        Returns:
            bool: 입장 성공 여부
        """
        if not room_name:
            self.logger.warning("방 이름이 제공되지 않았습니다.")
            return False
            
        # 중지 명령 확인
        if self._should_stop_process():
            return False
            
        self.logger.info(f"특정 방 '{room_name}' 입장 시도 시작")
        
        # iframe 매니저 초기화
        self.iframe_manager = IframeManager(self.devtools.driver)
        
        # 카지노 로비로 이동 및 준비
        if not self._prepare_casino_lobby():
            self.logger.error("카지노 로비 준비 실패")
            return False
            
        # 방 검색 및 입장 시도
        for attempt in range(max_retries):
            try:
                self.logger.info(f"방 '{room_name}' 입장 시도 {attempt + 1}/{max_retries}")
                
                # 방 입장 시도
                if self._search_and_enter_room(room_name):
                    # 입장 성공 후 게임 상태 검증
                    if self._validate_room_entry(room_name):
                        self.logger.info(f"방 '{room_name}' 입장 및 검증 완료")
                        return True
                    else:
                        self.logger.warning(f"방 '{room_name}' 입장 후 검증 실패")
                        # 방 나가기 시도
                        self._exit_current_room()
                else:
                    self.logger.warning(f"방 '{room_name}' 검색 또는 입장 실패")
                
                # 재시도 전 대기 및 페이지 상태 복구
                if attempt < max_retries - 1:
                    time.sleep(2)
                    self._prepare_casino_lobby()
                    
            except Exception as e:
                self.logger.error(f"방 '{room_name}' 입장 시도 중 오류: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    time.sleep(2)
                    self._prepare_casino_lobby()
        
        self.logger.error(f"방 '{room_name}' 입장 최종 실패 (최대 재시도 횟수 초과)")
        return False

    # 🚫 기존 복잡한 코드 전체를 다음으로 교체:
    def enter_room_from_server(self, streak_count=3):
        """서버에서 연패 방을 추천받아 입장"""
        try:
            if self._should_stop_process():
                return None
                
            current_time = time.time()
            if current_time - self.last_streak_room_request < self.streak_room_request_interval:
                remaining_time = self.streak_room_request_interval - (current_time - self.last_streak_room_request)
                self.logger.info(f"연패 방 요청 대기 중... (남은 시간: {remaining_time:.1f}초)")
                return None
            
            self.logger.info(f"서버에서 {streak_count}연패 방 검색 요청")
            
            # 🔥 통합 서버 클라이언트 사용
            response = self.server_client.find_streak_rooms(min_streak=streak_count)
            
            self.last_streak_room_request = current_time
            
            if not response or response.get('status') != 'success':
                error_msg = response.get('message', '알 수 없는 오류') if response else '서버 응답 없음'
                self.logger.warning(f"서버에서 연패 방 검색 실패: {error_msg}")
                return None
            
            streak_rooms = response.get('streak_rooms', [])
            if not streak_rooms:
                self.logger.info("서버에서 추천할 연패 방이 없습니다.")
                return None
            
            # 첫 번째 추천 방 선택하여 입장 시도
            target_room = streak_rooms[0]
            room_name = target_room.get('room_name')
            
            if self.enter_specific_room(room_name):
                return room_name
            else:
                self.logger.warning(f"서버 추천 방 '{room_name}' 입장 실패")
                return None
                    
        except Exception as e:
            self.logger.error(f"서버 기반 방 입장 중 오류: {e}")
            return None
        
    def enter_room(self, streak_count=3):
        """
        방 입장 메인 메서드 (서버 기반 + 레거시 호환)
        
        Args:
            streak_count (int): 연패 기준 (기본값 3)
        
        Returns:
            str: 선택된 방 이름 또는 None
        """
        # 중지 명령 확인
        if self._should_stop_process():
            return None
        
        # 우선 서버 기반 방 입장 시도
        room_name = self.enter_room_from_server(streak_count)
        if room_name:
            return room_name
        
        # 서버 기반 실패 시 레거시 방식으로 폴백
        self.logger.info("서버 기반 방 입장 실패, 레거시 방식으로 폴백")
        return self._legacy_enter_room()

    # services/room_entry_service.py에 추가할 메소드

    def enter_room_by_name(self, room_name: str) -> bool:
        """
        방 이름으로 직접 방 입장 (기존 enter_specific_room의 별칭)
        
        Args:
            room_name (str): 입장할 방 이름
            
        Returns:
            bool: 입장 성공 여부
        """
        return self.enter_specific_room(room_name)

    def _legacy_enter_room(self):
        """
        기존 방식의 방 입장 로직 (레거시 호환용)
        """
        max_attempts = 10
        attempts = 0
        
        # iframe 매니저 초기화
        self.iframe_manager = IframeManager(self.devtools.driver)
        self.consecutive_failures = 0
        
        while attempts < max_attempts:
            try:
                # 중지 명령 재확인
                if self._should_stop_process():
                    return None
                
                # 다음에 방문할 방 가져오기
                room_name = self.room_manager.get_next_room_to_visit()
                
                if not room_name:
                    QMessageBox.warning(self.main_window, "알림", "자동 매매를 시작할 방을 선택해주세요.")
                    return None
                
                # 방 이름에서 첫 번째 줄만 추출 (UI 표시용)
                display_name = room_name.split('\n')[0] if '\n' in room_name else room_name
                
                # 카지노 로비 상태 초기화
                if attempts > 0:
                    self._prepare_casino_lobby()
                
                # 방 검색 및 입장
                if not self._search_and_enter_room(room_name):
                    self.logger.warning(f"방 '{display_name}' 입장 실패, 다음 방 시도")
                    attempts += 1
                    self.consecutive_failures += 1
                    self.room_manager.mark_current_room_visited(room_name)
                    continue
                
                # 입장 성공 후 게임 상태 검증
                if self._validate_room_entry(room_name):
                    return room_name
                else:
                    # 검증 실패 시 방 나가기
                    self._exit_current_room()
                    self.room_manager.mark_room_visited(room_name)
                    attempts += 1
                    continue

            except Exception as e:
                self.logger.error(f"레거시 방 입장 중 오류 발생: {e}", exc_info=True)
                attempts += 1
                self.consecutive_failures += 1
                
                if attempts >= max_attempts:
                    QMessageBox.warning(
                        self.main_window, 
                        "방 입장 실패", 
                        f"여러 방에 입장을 시도했으나 모두 실패했습니다.\n최대 시도 횟수({max_attempts}회)를 초과했습니다."
                    )
                    return None
                
                time.sleep(2)
                continue
                    
        return None

    def _should_stop_process(self):
        """프로세스 중지 조건 확인"""
        if hasattr(self.main_window, 'trading_manager'):
            trading_manager = self.main_window.trading_manager
            
            # 전체 프로세스 중지 확인
            if hasattr(trading_manager, 'stop_all_processes') and trading_manager.stop_all_processes:
                return True
            
            # 목표 금액 도달 확인
            if (hasattr(trading_manager, 'balance_service') and 
                hasattr(trading_manager.balance_service, '_target_amount_reached') and 
                trading_manager.balance_service._target_amount_reached):
                return True
                
        return False

    def _prepare_casino_lobby(self):
        """카지노 로비 준비 및 상태 초기화"""
        try:
            # 창 목록 확인
            window_handles = self.devtools.driver.window_handles
            if len(window_handles) >= 2:
                # 카지노 로비 창으로 전환
                self.devtools.driver.switch_to.window(window_handles[1])
                time.sleep(1)
                
                # 새로고침 필요성 판단
                current_time = time.time()
                should_refresh = (
                    current_time - self.last_refresh_time > self.refresh_interval and 
                    (self.consecutive_failures >= 2)
                )
                
                if should_refresh:
                    self.logger.info("카지노 로비 페이지 새로고침")
                    self.devtools.driver.refresh()
                    time.sleep(3)
                    self.last_refresh_time = current_time
                    self.consecutive_failures = 0
                
                return True
            else:
                self.logger.warning("카지노 로비 창을 찾을 수 없습니다.")
                return False
                
        except Exception as e:
            self.logger.error(f"카지노 로비 준비 중 오류: {e}")
            return False

    def _validate_room_entry(self, room_name):
        """방 입장 후 게임 상태 검증"""
        try:
            time.sleep(2)  # 방 입장 후 충분히 대기
            
            # 게임 상태 확인 (최대 3회 시도)
            retry_state_check = 3
            game_state = None
            
            for i in range(retry_state_check):
                try:
                    if hasattr(self.main_window, 'trading_manager') and hasattr(self.main_window.trading_manager, 'game_monitoring_service'):
                        game_state = self.main_window.trading_manager.game_monitoring_service.get_current_game_state()
                        if game_state:
                            break
                    time.sleep(1)
                except Exception as e:
                    self.logger.warning(f"게임 상태 확인 {i+1}번째 시도 실패: {e}")
                    time.sleep(1)
            
            if not game_state:
                self.logger.warning("게임 상태를 확인할 수 없습니다.")
                return False
            
            game_count = game_state.get('round', 0)
            
            # ChoicePickSystem 업데이트
            if hasattr(self.main_window.trading_manager, 'choice_pick_system'):
                cps = self.main_window.trading_manager.choice_pick_system
                cps._entered_round = game_count
                cps._current_game_round = game_count
                self.logger.info(f"[방 입장] ChoicePickSystem에 _entered_round={game_count}, _current_game_round={game_count} 설정")
            
            # # 게임 수 범위 확인 (16-57판)
            # if game_count < 16 or game_count > 57:
            #     self.logger.info(f"방 '{room_name}' 게임 수({game_count})가 범위(16-57) 밖입니다.")
            #     return False
            
            # UI 업데이트
            self.main_window.update_betting_status(room_name=room_name)
            
            return True
            
        except Exception as e:
            self.logger.error(f"방 입장 검증 중 오류: {e}", exc_info=True)
            return False

    def _exit_current_room(self):
        """현재 방에서 나가기"""
        try:
            if hasattr(self.main_window, 'trading_manager') and hasattr(self.main_window.trading_manager, 'game_monitoring_service'):
                if self.main_window.trading_manager.game_monitoring_service.close_current_room():
                    # 카지노 로비로 포커싱
                    window_handles = self.devtools.driver.window_handles
                    if len(window_handles) >= 2:
                        self.devtools.driver.switch_to.window(window_handles[1])
                    return True
                else:
                    self.logger.error("방 나가기 실패")
                    return False
            return False
        except Exception as e:
            self.logger.error(f"방 나가기 중 오류: {e}")
            return False

    def _search_and_enter_room(self, room_name, max_retries=3):
        """방 검색 및 입장 (기존 로직 유지하되 개선)"""
        refresh_needed = False
        
        for retry_count in range(max_retries):
            try:
                # 방 이름 전처리 - 첫 줄만 사용
                search_name = room_name.split('\n')[0].strip()
                
                # 페이지 새로고침 (필요한 경우에만)
                if retry_count > 0 and refresh_needed:
                    self._refresh_page_if_needed()
                    refresh_needed = False
                
                # iframe 처리
                if not self._handle_iframe_navigation():
                    refresh_needed = True
                    continue
                
                # 검색 입력 필드 찾기
                search_input = self._find_search_input()
                if not search_input:
                    self.logger.warning("검색 입력 필드를 찾을 수 없음")
                    refresh_needed = True
                    self.devtools.driver.switch_to.default_content()
                    continue
                
                # 검색 실행
                if not self._execute_search(search_input, search_name):
                    refresh_needed = True
                    continue
                
                # 검색 결과 처리 및 클릭
                if not self._handle_search_results():
                    refresh_needed = True
                    continue
                
                # 새 창 전환 확인
                if self._switch_to_new_window():
                    return True
                else:
                    refresh_needed = True
                    continue

            except Exception as e:
                self.logger.error(f"방 검색 및 입장 중 오류: {e}")
                refresh_needed = True
                if retry_count < max_retries - 1:
                    time.sleep(2)
                else:
                    self.logger.warning(f"최대 시도 횟수 초과로 방 '{room_name}' 입장 실패")
                    return False
        
        return False

    def _refresh_page_if_needed(self):
        """필요한 경우 페이지 새로고침"""
        try:
            current_time = time.time()
            if current_time - self.last_refresh_time > self.refresh_interval:
                self.devtools.driver.refresh()
                time.sleep(3)
                self.last_refresh_time = current_time
        except Exception as e:
            self.logger.warning(f"페이지 새로고침 중 오류: {e}")

    def _handle_iframe_navigation(self):
        """iframe 탐색 및 전환 처리"""
        try:
            # 기본 프레임으로 전환
            self.devtools.driver.switch_to.default_content()
            
            # iframe 처리
            iframes = self.devtools.driver.find_elements(By.TAG_NAME, "iframe")
            
            if len(iframes) > 0:
                # 첫 번째 iframe으로 전환
                self.devtools.driver.switch_to.frame(iframes[0])
                
                # 중첩된 iframe 확인
                nested_iframes = self.devtools.driver.find_elements(By.TAG_NAME, "iframe")
                
                if len(nested_iframes) > 0:
                    # 첫 번째 중첩 iframe으로 전환
                    self.devtools.driver.switch_to.frame(nested_iframes[0])
                
                return True
            else:
                # 유틸리티 함수 사용
                return switch_to_iframe_with_retry(self.devtools.driver, max_retries=3, max_depth=2)
                
        except Exception as e:
            self.logger.warning(f"iframe 탐색 중 오류: {e}")
            return False

    def _execute_search(self, search_input, search_name):
        """검색 실행"""
        try:
            time.sleep(1)
            search_input.clear()
            search_input.send_keys(search_name)
            time.sleep(2)  # 검색 결과 대기
            return True
        except Exception as e:
            self.logger.warning(f"검색 실행 중 오류: {e}")
            return False

    def _handle_search_results(self):
        """검색 결과 처리 및 클릭"""
        try:
            # CSS 선택자로 검색 결과 찾기
            result_selectors = [
                "div.SearchResult--28235[data-role='search-result']",
                "div[data-role='search-result']",
                "div.search-result",
                "div.game-result-item"
            ]
            
            search_results = []
            for selector in result_selectors:
                try:
                    results = WebDriverWait(self.devtools.driver, 3).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                    )
                    if results:
                        search_results = results
                        break
                except:
                    continue
            
            # 검색 결과 클릭
            if search_results and len(search_results) > 0:
                search_results[0].click()
                return True
            else:
                # JavaScript로 재시도
                return self._click_search_result_with_js()
                
        except Exception as e:
            self.logger.warning(f"검색 결과 처리 중 오류: {e}")
            return False

    def _click_search_result_with_js(self):
        """JavaScript를 사용한 검색 결과 클릭"""
        try:
            js_script = """
                var selectors = [
                    "div[data-role='search-result']",
                    "div.SearchResult--28235",
                    "div.search-result",
                    "div.game-result-item"
                ];
                
                for (var i = 0; i < selectors.length; i++) {
                    var results = document.querySelectorAll(selectors[i]);
                    if (results && results.length > 0) {
                        results[0].click();
                        return true;
                    }
                }
                return false;
            """
            
            clicked = self.devtools.driver.execute_script(js_script)
            return clicked
            
        except Exception as e:
            self.logger.warning(f"JavaScript 검색 결과 클릭 중 오류: {e}")
            return False

    def _switch_to_new_window(self):
        """새 창으로 전환"""
        try:
            time.sleep(3)  # 새 창 로드 대기
            new_window_handles = self.devtools.driver.window_handles
            
            if len(new_window_handles) > 1:
                self.devtools.driver.switch_to.window(new_window_handles[-1])
                time.sleep(1)
                return True
            else:
                self.logger.warning("새 창이 열리지 않았습니다.")
                return False
                
        except Exception as e:
            self.logger.warning(f"창 전환 중 오류: {e}")
            return False

    def _find_search_input(self):
        """검색 입력 필드를 다양한 방법으로 찾는 헬퍼 메서드 (기존 로직 유지)"""
        search_input = None
        
        # 방법 1: 기본 선택자들
        search_selectors = [
            "input.TableTextInput--464ac",
            "input[data-role='search-input']",
            "input[placeholder='찾기']",
            "input.search-input"
        ]
        
        for selector in search_selectors:
            try:
                search_input = self.devtools.driver.find_element(By.CSS_SELECTOR, selector)
                if search_input:
                    return search_input
            except:
                continue
        
        # 방법 2: 복합 선택자
        try:
            composite_selector = "input.TableTextInput--464ac[placeholder='찾기'][data-role='search-input']"
            search_input = self.devtools.driver.find_element(By.CSS_SELECTOR, composite_selector)
            if search_input:
                return search_input
        except:
            pass
        
        # 방법 3: 모든 input 요소 확인
        try:
            all_inputs = self.devtools.driver.find_elements(By.TAG_NAME, "input")
            
            for input_el in all_inputs:
                try:
                    input_type = input_el.get_attribute("type") or ""
                    input_class = input_el.get_attribute("class") or ""
                    input_placeholder = input_el.get_attribute("placeholder") or ""
                    
                    # 검색 관련 특징 확인
                    if (input_type.lower() == "text" or input_type == "") and \
                    (input_placeholder.lower() == "찾기" or \
                        "search" in input_class.lower() or \
                        "search" in input_placeholder.lower()):
                        return input_el
                except:
                    continue
        except Exception as e:
            self.logger.warning(f"모든 input 요소 검색 실패: {e}")
        
        # 방법 4: XPath 사용
        try:
            xpath_expressions = [
                "//input[@placeholder='찾기']",
                "//input[@data-role='search-input']",
                "//input[contains(@class, 'TableTextInput')]",
                "//input[contains(@class, 'search')]",
                "//div[contains(@class, 'search')]//input"
            ]
            
            for xpath in xpath_expressions:
                try:
                    input_el = self.devtools.driver.find_element(By.XPATH, xpath)
                    if input_el:
                        return input_el
                except:
                    continue
        except Exception as e:
            self.logger.warning(f"XPath 검색 실패: {e}")
        
        # 방법 5: JavaScript로 검색
        try:
            js_code = """
            // 모든 input 요소 찾기
            var inputs = document.getElementsByTagName('input');
            
            // 검색 관련 input 필터링
            for (var i = 0; i < inputs.length; i++) {
                var input = inputs[i];
                if (input.placeholder === '찾기' || 
                    input.getAttribute('data-role') === 'search-input' ||
                    (input.className && input.className.includes('TableTextInput'))) {
                    return input;
                }
            }
            
            // 아무 input이라도 있으면 첫 번째 반환
            return inputs.length > 0 ? inputs[0] : null;
            """
            
            input_el = self.devtools.driver.execute_script(js_code)
            if input_el:
                return input_el
        except Exception as e:
            self.logger.warning(f"JavaScript 검색 실패: {e}")
        
        return None

    def get_server_monitoring_status(self):
        """서버 모니터링 상태 확인"""
        try:
            # 서버 상태 확인 로직 (필요시 구현)
            return {
                'monitoring_active': self.current_monitoring_session is not None,
                'last_streak_request': self.last_streak_room_request,
                'consecutive_failures': self.consecutive_failures
            }
        except Exception as e:
            self.logger.error(f"서버 모니터링 상태 확인 중 오류: {e}")
            return None

    def reset_server_session(self):
        """서버 세션 초기화"""
        try:
            self.current_monitoring_session = None
            self.last_streak_room_request = 0
            self.consecutive_failures = 0
            self.logger.info("서버 세션이 초기화되었습니다.")
        except Exception as e:
            self.logger.error(f"서버 세션 초기화 중 오류: {e}")