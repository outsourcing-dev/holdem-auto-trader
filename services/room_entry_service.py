import random
import time
import logging
import re
from PyQt6.QtWidgets import QMessageBox
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.iframe_utils import IframeManager, switch_to_iframe_with_retry

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
        
        # iframe 매니저 초기화
        self.iframe_manager = None
        
        # 새로고침 관련 상태 변수 추가
        self.last_refresh_time = 0
        self.refresh_interval = 60  # 새로고침 사이의 최소 간격(초)
        self.consecutive_failures = 0

    def enter_room(self):
        """
        랜덤 순서로 생성된 방 목록에서 다음 방에 입장합니다.
        방 게임 수가 10판 미만이거나 50판 이상이면 다른 방을 찾습니다.
        
        Returns:
            str: 선택된 방 이름 또는 None
        """
        if hasattr(self.main_window, 'trading_manager'):
            if hasattr(self.main_window.trading_manager, 'stop_all_processes') and self.main_window.trading_manager.stop_all_processes:
                # self.logger.info("중지 명령이 감지되어 방 입장을 중단합니다.")
                return None
            
            # 목표 금액 도달 확인도 추가
            if hasattr(self.main_window.trading_manager, 'balance_service') and hasattr(self.main_window.trading_manager.balance_service, '_target_amount_reached') and self.main_window.trading_manager.balance_service._target_amount_reached:
                # self.logger.info("목표 금액 도달이 감지되어 방 입장을 중단합니다.")
                return None
            
        max_attempts = 10  # 최대 방 찾기 시도 횟수 
        attempts = 0
        
        # iframe 매니저 초기화 (driver 객체가 변경될 수 있으므로 여기서 다시 초기화)
        self.iframe_manager = IframeManager(self.devtools.driver)
        
        # 연속 실패 횟수 초기화
        self.consecutive_failures = 0
        
        while attempts < max_attempts:
            try:
                # 다음에 방문할 방 가져오기
                room_name = self.room_manager.get_next_room_to_visit()
                
                if not room_name:
                    QMessageBox.warning(self.main_window, "알림", "자동 매매를 시작할 방을 선택해주세요.")
                    return None
                
                # 방 이름에서 첫 번째 줄만 추출 (UI 표시용)
                display_name = room_name.split('\n')[0] if '\n' in room_name else room_name
                
                # 카지노 로비 상태 초기화 시도 (시도 횟수가 증가한 경우에만)
                if attempts > 0:
                    # 창 목록 확인
                    window_handles = self.devtools.driver.window_handles
                    if len(window_handles) >= 2:
                        # 카지노 로비 창으로 전환 시도
                        self.devtools.driver.switch_to.window(window_handles[1])
                        time.sleep(1)
                        
                        # 새로고침 간격 조건 추가 (마지막 새로고침 후 최소 시간이 지났고, 실패 횟수가 임계값을 넘었을 때만)
                        current_time = time.time()
                        if (current_time - self.last_refresh_time > self.refresh_interval and 
                            (self.consecutive_failures >= 2 or attempts % 5 == 0)):  # 연속 2번 실패했거나 5번째 시도마다
                            # self.logger.info("카지노 로비 페이지 새로고침")
                            self.devtools.driver.refresh()
                            time.sleep(3)
                            self.last_refresh_time = current_time
                            self.consecutive_failures = 0  # 새로고침 후 카운터 리셋

                # 방 검색 및 입장 (원본 방 이름 전체 사용)
                if not self._search_and_enter_room(room_name):
                    # 검색 실패 시 다음 방 시도
                    self.logger.warning(f"방 '{display_name}' 입장 실패, 다음 방 시도")
                    attempts += 1
                    self.consecutive_failures += 1
                    # 방문 처리하여 다음 방을 가져오도록 함
                    self.room_manager.mark_current_room_visited(room_name)
                    continue
                
                # 성공하면 연속 실패 카운터 리셋
                self.consecutive_failures = 0
                
                # 방 입장 후 게임 수 확인
                time.sleep(2)  # 방 입장 후 충분히 대기
                
                # 게임 상태 확인
                retry_state_check = 3
                game_state = None
                
                # 게임 상태 확인 여러 번 시도
                for i in range(retry_state_check):
                    try:
                        game_state = self.main_window.trading_manager.game_monitoring_service.get_current_game_state()
                        if game_state:
                            break
                        time.sleep(1)
                    except Exception as e:
                        self.logger.warning(f"게임 상태 확인 {i+1}번째 시도 실패: {e}")
                        time.sleep(1)
                
                if game_state:
                    game_count = game_state.get('round', 0)
                    
                    # 입장 기준 설정 (65로 상향 조정됨)
                    if game_count < 10 or game_count > 65:
                        # 방 나가기
                        if self.main_window.trading_manager.game_monitoring_service.close_current_room():
                            # 방문 처리하여 다음에 다시 시도하지 않도록 함
                            self.room_manager.mark_room_visited(room_name)
                            
                            # 2번 창(카지노 로비)으로 포커싱
                            window_handles = self.devtools.driver.window_handles
                            if len(window_handles) >= 2:
                                self.devtools.driver.switch_to.window(window_handles[1])
                            
                            attempts += 1
                            continue
                        else:
                            self.logger.error("방 나가기 실패")
                            return None
                
                # 성공한 경우 원본 방 이름 반환 (전체 정보 유지)
                return room_name

            except Exception as e:
                # 오류 로깅 및 처리
                self.logger.error(f"방 입장 중 오류 발생: {e}", exc_info=True)
                
                attempts += 1
                self.consecutive_failures += 1
                
                if attempts >= max_attempts:
                    QMessageBox.warning(
                        self.main_window, 
                        "방 입장 실패", 
                        f"여러 방에 입장을 시도했으나 모두 실패했습니다.\n최대 시도 횟수({max_attempts}회)를 초과했습니다."
                    )
                    return None
                
                time.sleep(2)  # 다음 시도 전 잠시 대기
                continue
                    
        return None  # 모든 시도 실패

    def _search_and_enter_room(self, room_name, max_retries=3):
        """방 검색 및 입장 (재시도 로직 포함)"""
        # 방 재시도마다 매번 새로고침하지 않도록 수정
        refresh_needed = False
        
        for retry_count in range(max_retries):
            try:
                # 방 이름 전처리 - 첫 줄만 사용
                search_name = room_name.split('\n')[0].strip()
                
                # 페이지 새로고침 (첫 시도가 아니고 refresh_needed가 True인 경우에만)
                if retry_count > 0 and refresh_needed:
                    try:
                        # 마지막 새로고침 이후 충분한 시간이 경과했는지 확인
                        current_time = time.time()
                        if current_time - self.last_refresh_time > self.refresh_interval:
                            # self.logger.info(f"페이지 새로고침 후 재시도 중...")
                            self.devtools.driver.refresh()
                            time.sleep(3)  # 페이지 로드 대기
                            self.last_refresh_time = current_time
                            refresh_needed = False
                    except Exception as e:
                        self.logger.warning(f"페이지 새로고침 중 오류: {e}")
                
                # 기본 프레임으로 전환
                self.devtools.driver.switch_to.default_content()
                
                # iframe 처리를 위한 flag
                inside_iframe = False
                
                try:
                    # 기본 컨텐츠에서 모든 iframe 태그 찾기
                    iframes = self.devtools.driver.find_elements(By.TAG_NAME, "iframe")
                    
                    if len(iframes) > 0:
                        # 첫 번째 iframe으로 전환
                        self.devtools.driver.switch_to.frame(iframes[0])
                        inside_iframe = True
                        
                        # 중첩된 iframe이 있는지 확인
                        nested_iframes = self.devtools.driver.find_elements(By.TAG_NAME, "iframe")
                        
                        if len(nested_iframes) > 0:
                            # 첫 번째 중첩 iframe으로 전환
                            self.devtools.driver.switch_to.frame(nested_iframes[0])
                    else:
                        self.logger.warning("최상위에서 iframe을 찾을 수 없음")
                except Exception as e:
                    self.logger.warning(f"iframe 전환 중 오류: {e}")
                    # 오류 발생 시 기본 컨텐츠로 복귀
                    self.devtools.driver.switch_to.default_content()
                    inside_iframe = False
                
                # iframe 전환 실패 시 유틸리티 사용
                if not inside_iframe:
                    inside_iframe = switch_to_iframe_with_retry(self.devtools.driver, max_retries=3, max_depth=2)
                    
                    if not inside_iframe:
                        self.logger.warning("모든 iframe 전환 방법 실패. 기본 컨텐츠 상태로 계속 진행")
                        # iframe 전환 실패 시 새로고침 필요 표시
                        refresh_needed = True
                
                # 검색 입력 필드 찾기
                search_input = self._find_search_input()
                
                if not search_input:
                    self.logger.warning("검색 입력 필드를 찾을 수 없음. 다음 시도로 넘어감")
                    # 검색 입력 필드를 찾지 못하면 새로고침 필요 표시
                    refresh_needed = True
                    # 기본 컨텐츠로 복귀 시도
                    self.devtools.driver.switch_to.default_content()
                    continue
                
                # 검색 입력 필드에 방 이름 입력
                time.sleep(1)
                search_input.clear()
                search_input.send_keys(search_name)
                
                # 검색 결과가 나타날 때까지 충분히 대기
                time.sleep(2)
                
                # 검색 결과 찾기 시도
                try:
                    # 여러 선택자로 검색 결과 찾기
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
                    
                    # 검색 결과가 있는지 확인
                    if search_results and len(search_results) > 0:
                        search_results[0].click()
                    else:
                        # JavaScript로 다시 시도
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
                        
                        if not clicked:
                            # 검색 결과가 없으면 새로고침 필요 표시
                            refresh_needed = True
                            self.logger.warning(f"'{search_name}' 검색 결과가 없습니다. 다른 방법을 시도합니다.")
                            continue  # 다음 재시도로 넘어감
                except Exception as e:
                    refresh_needed = True
                    self.logger.warning(f"검색 결과 처리 중 오류: {e}")
                    continue  # 다음 재시도로 넘어감

                # 새 창으로 전환
                try:
                    time.sleep(3)  # 새 창이 로드될 때까지 충분히 대기
                    new_window_handles = self.devtools.driver.window_handles
                    
                    if len(new_window_handles) > 1:
                        self.devtools.driver.switch_to.window(new_window_handles[-1])
                        time.sleep(1)
                        
                        # UI 업데이트
                        self.main_window.update_betting_status(room_name=room_name)
                        return True
                    else:
                        refresh_needed = True
                        self.logger.warning("새 창이 열리지 않았습니다. 다시 시도합니다.")
                        continue  # 다음 재시도로 넘어감
                except Exception as e:
                    refresh_needed = True
                    self.logger.warning(f"창 전환 중 오류: {e}")
                    continue  # 다음 재시도로 넘어감

            except Exception as e:
                self.logger.error(f"방 검색 및 입장 중 오류: {e}")
                refresh_needed = True
                # 마지막 시도가 아니면 재시도
                if retry_count < max_retries - 1:
                    time.sleep(2)  # 재시도 전 대기
                else:
                    # 모든 시도 실패
                    self.logger.warning(f"최대 시도 횟수 초과로 방 '{room_name}' 입장 실패")
                    return False
        
        # 모든 시도 실패
        return False

    def _find_search_input(self):
        """검색 입력 필드를 다양한 방법으로 찾는 헬퍼 메서드"""
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