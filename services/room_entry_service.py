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
        방 게임 수가 10판 미만이거나 50판 이상이면 다른 방을 찾습니다.
        
        Returns:
            str: 선택된 방 이름 또는 None
        """
        max_attempts = 10  # 최대 방 찾기 시도 횟수 증가
        attempts = 0
        
        while attempts < max_attempts:
            try:
                # 다음에 방문할 방 가져오기
                room_name = self.room_manager.get_next_room_to_visit()
                
                if not room_name:
                    QMessageBox.warning(self.main_window, "알림", "자동 매매를 시작할 방을 선택해주세요.")
                    return None
                
                # 방 이름에서 첫 번째 줄만 추출 (UI 표시용)
                display_name = room_name.split('\n')[0] if '\n' in room_name else room_name
                
                # 로깅
                self.logger.info(f"선택된 방: {display_name} (시도 {attempts + 1}/{max_attempts})")

                # 카지노 로비 상태 초기화 시도 (시도 횟수가 증가한 경우에만)
                if attempts > 0:
                    try:
                        # 창 목록 확인
                        window_handles = self.devtools.driver.window_handles
                        if len(window_handles) >= 2:
                            # 카지노 로비 창으로 전환 시도
                            self.devtools.driver.switch_to.window(window_handles[1])
                            self.logger.info("카지노 로비 창으로 포커싱 전환")
                            time.sleep(1)
                            
                            # 페이지 새로고침 시도 (필요시)
                            if attempts % 3 == 0:  # 3번마다 한 번씩 새로고침
                                self.logger.info("카지노 로비 페이지 새로고침")
                                self.devtools.driver.refresh()
                                time.sleep(3)
                    except Exception as e:
                        self.logger.warning(f"카지노 로비 초기화 시도 중 오류: {e}")

                # 방 검색 및 입장 (원본 방 이름 전체 사용)
                # 수정: 성공 여부 반환값 확인
                if not self._search_and_enter_room(room_name):
                    # 검색 실패 시 다음 방 시도
                    self.logger.warning(f"방 '{display_name}' 입장 실패, 다음 방 시도")
                    attempts += 1
                    # 방문 처리하여 다음 방을 가져오도록 함
                    self.room_manager.mark_current_room_visited(room_name)
                    continue
                
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
                    self.logger.info(f"방 {display_name}의 현재 게임 수: {game_count}")
                    
                    # 게임 수가 10판 미만이거나 50판 이상인 경우 방 나가기
                    if game_count < 10 or game_count > 50:
                        self.logger.info(f"게임 수가 적합하지 않음 ({game_count}판). 다른 방을 찾습니다.")
                        
                        # 방 나가기
                        if self.main_window.trading_manager.game_monitoring_service.close_current_room():
                            self.logger.info("방을 성공적으로 나갔습니다.")
                            
                            # 방문 처리하여 다음에 다시 시도하지 않도록 함
                            self.room_manager.mark_room_visited(room_name)
                            
                            # 2번 창(카지노 로비)으로 포커싱
                            window_handles = self.devtools.driver.window_handles
                            if len(window_handles) >= 2:
                                self.devtools.driver.switch_to.window(window_handles[1])
                                self.logger.info("카지노 로비 창으로 포커싱 전환")
                            
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
                if attempts >= max_attempts:
                    QMessageBox.warning(
                        self.main_window, 
                        "방 입장 실패", 
                        f"여러 방에 입장을 시도했으나 모두 실패했습니다.\n최대 시도 횟수({max_attempts}회)를 초과했습니다."
                    )
                    return None
                
                self.logger.info(f"다음 방 시도 중... ({attempts}/{max_attempts})")
                time.sleep(2)  # 다음 시도 전 잠시 대기
                continue
                    
        return None  # 모든 시도 실패

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
        
    def _search_and_enter_room(self, room_name, max_retries=3):
        """방 검색 및 입장 (재시도 로직 포함)"""
        for retry_count in range(max_retries):
            try:
                # 방 이름 전처리 - 첫 줄만 사용
                search_name = room_name.split('\n')[0].strip()
                self.logger.info(f"검색할 방 이름: '{search_name}' (원본: '{room_name}') - 시도 {retry_count+1}/{max_retries}")
                
                # 페이지 새로고침 (첫 시도가 아닌 경우)
                if retry_count > 0:
                    try:
                        self.logger.info(f"페이지 새로고침 후 재시도 중...")
                        self.devtools.driver.refresh()
                        time.sleep(3)  # 페이지 로드 대기
                    except Exception as e:
                        self.logger.warning(f"페이지 새로고침 중 오류: {e}")
                
                # iframe으로 전환
                try:
                    self.devtools.driver.switch_to.default_content()
                    # 명시적 대기 추가
                    WebDriverWait(self.devtools.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "iframe"))
                    )
                    iframe = self.devtools.driver.find_element(By.CSS_SELECTOR, "iframe")
                    self.devtools.driver.switch_to.frame(iframe)
                    self.logger.info("iframe으로 성공적으로 전환")
                    time.sleep(1)  # iframe 전환 후 추가 대기
                except Exception as e:
                    self.logger.warning(f"iframe 전환 중 오류: {e}")
                    continue  # 다음 재시도로 넘어감
                
                # 검색 입력 필드 찾기 - 명시적 대기 추가
                try:
                    # 여러 선택자 시도 (대체 전략)
                    search_selectors = [
                        "input.TableTextInput--464ac",
                        "input[data-role='search-input']",
                        "input[placeholder='찾기']",
                        "input.search-input"
                    ]
                    
                    search_input = None
                    for selector in search_selectors:
                        try:
                            self.logger.info(f"검색 입력 필드 선택자 시도: {selector}")
                            search_input = WebDriverWait(self.devtools.driver, 3).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                            )
                            if search_input:
                                self.logger.info(f"검색 입력 필드 발견: {selector}")
                                break
                        except:
                            continue
                    
                    if not search_input:
                        raise Exception("모든 검색 입력 필드 선택자가 실패했습니다.")
                    
                    time.sleep(1)  # 검색 입력 필드 발견 후 추가 대기
                    search_input.clear()
                    search_input.send_keys(search_name)
                    self.logger.info(f"방 이름 '{search_name}' 입력 완료")
                    
                    # 검색 결과가 나타날 때까지 충분히 대기
                    time.sleep(3)
                except Exception as e:
                    self.logger.warning(f"검색 입력 필드 찾기 또는 입력 중 오류: {e}")
                    continue  # 다음 재시도로 넘어감
                
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
                                self.logger.info(f"검색 결과 발견 ({len(results)}개): {selector}")
                                break
                        except:
                            continue
                    
                    # 검색 결과가 있는지 확인
                    if search_results and len(search_results) > 0:
                        # 첫 번째 요소 클릭 (배열의 0번 인덱스)
                        self.logger.info(f"검색 결과 {len(search_results)}개 발견, 첫 번째 결과 클릭")
                        search_results[0].click()
                    else:
                        # JavaScript로 다시 시도
                        self.logger.info("JavaScript로 검색 결과 찾기 시도")
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
                            # 수정: 예외를 발생시키는 대신 False 반환
                            self.logger.warning(f"'{search_name}' 검색 결과가 없습니다. 다른 방법을 시도합니다.")
                            continue  # 다음 재시도로 넘어감
                except Exception as e:
                    self.logger.warning(f"검색 결과 처리 중 오류: {e}")
                    continue  # 다음 재시도로 넘어감

                # 새 창으로 전환
                try:
                    time.sleep(3)  # 새 창이 로드될 때까지 충분히 대기
                    new_window_handles = self.devtools.driver.window_handles
                    
                    if len(new_window_handles) > 1:
                        self.devtools.driver.switch_to.window(new_window_handles[-1])
                        time.sleep(2)
                        
                        # UI 업데이트
                        self.main_window.update_betting_status(room_name=room_name)
                        self.logger.info(f"방 '{room_name}' 성공적으로 입장")
                        return True
                    else:
                        self.logger.warning("새 창이 열리지 않았습니다. 다시 시도합니다.")
                        continue  # 다음 재시도로 넘어감
                except Exception as e:
                    self.logger.warning(f"창 전환 중 오류: {e}")
                    continue  # 다음 재시도로 넘어감

            except Exception as e:
                self.logger.error(f"방 검색 및 입장 중 오류: {e}")
                # 마지막 시도가 아니면 재시도
                if retry_count < max_retries - 1:
                    self.logger.info(f"재시도 중... ({retry_count+1}/{max_retries})")
                    time.sleep(2)  # 재시도 전 대기
                else:
                    # 모든 시도 실패
                    self.logger.warning(f"최대 시도 횟수 초과로 방 '{room_name}' 입장 실패")
                    return False
        
        # 모든 시도 실패
        return False