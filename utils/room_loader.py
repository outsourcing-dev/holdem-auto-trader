from PyQt6.QtCore import QThread, pyqtSignal
import time
import re

def clean_text(text):
    """숨겨진 특수 문자 제거"""
    return re.sub(r'[\u200c\u2066\u2069]', '', text).strip()

class RoomLoaderThread(QThread):
    progress_signal = pyqtSignal(str, int)  
    found_room_signal = pyqtSignal(str)  
    finished_signal = pyqtSignal(list)  

    def __init__(self, devtools, filter_type="speed"):
        super().__init__()
        self.devtools = devtools
        self.filter_type = filter_type  
        self.stop_requested = False

    def run(self):
        all_rooms = []
        unique_rooms = set()  # 중복 방지를 위한 세트
        
        try:
            self.progress_signal.emit("방 목록을 불러오는 중...", 0)
            self.devtools.driver.switch_to.default_content()
            time.sleep(1)

            # iframe 존재 여부 확인 후 전환
            iframes = self.devtools.driver.find_elements("css selector", "iframe")
            if iframes:
                self.progress_signal.emit("iframe 전환 중...", 0)
                try:
                    self.devtools.driver.switch_to.frame(iframes[0])
                    time.sleep(1)
                except:
                    self.devtools.driver.switch_to.default_content()
            
            if self.filter_type == "speed":
                self._apply_speed_filter()
            
            self.progress_signal.emit("방 목록 스크롤 시작...", 0)
            
            # 스크롤 컨테이너 찾기 - 다양한 선택자 시도
            scroll_container = self._find_scroll_container()
            
            # 초기 높이 확인
            last_height = self.devtools.driver.execute_script("return arguments[0].scrollHeight", scroll_container)
            
            # 여러 선택자로 방 찾기 함수
            def find_rooms():
                selectors = [
                    ".tile--5d2e6", 
                    ".game-tile", 
                    "[data-role='game-tile']", 
                    "[class*='tile']", 
                    "div.lobby-table__game",
                    # 추가 선택자들
                    ".game-tile-container",
                    "[data-testid='game-tile']",
                    "div[data-game-id]"
                ]
                return self._find_elements_by_multiple_selectors(selectors)

            # 최초 방 목록 수집
            room_elements = find_rooms()
            initial_count = len(room_elements)
            self.progress_signal.emit(f"초기 방 개수: {initial_count}개 발견", initial_count)
            
            # 현재 보이는 방 목록 수집 및 추가
            visible_rooms = self._get_current_visible_rooms(room_elements)
            for room in visible_rooms:
                if room not in unique_rooms:
                    unique_rooms.add(room)
                    all_rooms.append(room)
                    self.found_room_signal.emit(room)
            
            self.progress_signal.emit(f"현재까지 발견된 방: {len(all_rooms)}개", len(all_rooms))
            
            # 스크롤 파라미터 설정
            max_scroll_attempts = 5  # 최대 스크롤 시도 횟수 증가
            no_new_rooms_count = 0
            scroll_attempts = 0

            # 스크롤 다운하면서 새로운 방 목록 수집
            while scroll_attempts < max_scroll_attempts and no_new_rooms_count < 3:
                if self.stop_requested:
                    self.progress_signal.emit("사용자에 의해 중단됨", len(all_rooms))
                    break
                
                # 스크롤 다운 - 여러 방법 시도
                self._scroll_down_enhanced(scroll_container)
                time.sleep(0.2)  # 로딩 대기 시간
                
                # 새 높이 확인
                new_height = self.devtools.driver.execute_script("return arguments[0].scrollHeight", scroll_container)
                current_scroll = self.devtools.driver.execute_script("return arguments[0].scrollTop", scroll_container)
                
                # 로그 추가
                self.progress_signal.emit(f"스크롤 진행 중... ({scroll_attempts+1}/{max_scroll_attempts}) - 높이: {current_scroll}/{new_height}", len(all_rooms))
                
                # 새로운 요소들 찾기
                room_elements = find_rooms()
                visible_rooms = self._get_current_visible_rooms(room_elements)
                
                # 새로운 방 찾기
                new_found = False
                for room in visible_rooms:
                    if room not in unique_rooms:
                        unique_rooms.add(room)
                        all_rooms.append(room)
                        self.found_room_signal.emit(room)
                        new_found = True
                
                # 새로운 방을 찾았는지 확인
                if new_found:
                    self.progress_signal.emit(f"새로운 방 발견! 현재까지 총 {len(all_rooms)}개", len(all_rooms))
                    no_new_rooms_count = 0
                else:
                    no_new_rooms_count += 1
                    self.progress_signal.emit(f"새로운 방 없음 ({no_new_rooms_count}/3)", len(all_rooms))
                
                # 스크롤이 끝에 도달했는지 확인
                if new_height == last_height and current_scroll + 100 >= new_height:
                    self.progress_signal.emit("스크롤 끝에 도달함", len(all_rooms))
                    no_new_rooms_count += 1
                
                last_height = new_height
                scroll_attempts += 1

            # 최종 필터링
            filtered_rooms = self._filter_rooms(all_rooms)
            # 스크롤을 최상단으로 이동
            result_rooms = [{"name": room, "checked": True} for room in filtered_rooms]
            self.progress_signal.emit(f"총 {len(filtered_rooms)}개 방 목록 로드 완료", len(filtered_rooms))
            self.finished_signal.emit(result_rooms)

        except Exception as e:
            self.progress_signal.emit(f"오류 발생: {str(e)}", len(all_rooms))
            self.finished_signal.emit([{"name": room, "checked": True} for room in all_rooms] if all_rooms else [])

    def _apply_speed_filter(self):
        """스피드 필터 적용"""
        self.progress_signal.emit("스피드 필터 적용 중...", 0)
        
        try:
            # 방법 1: 제공된 정확한 선택자 사용
            try:
                # 정확한 선택자로 라벨 찾기
                speed_label = self.devtools.driver.find_element("css selector", 
                    "label[for='speed'] span.Typography--d2c9a[data-role='typography']")
                
                if speed_label:
                    self.progress_signal.emit(f"정확한 스피드 라벨 발견: '{speed_label.text}'", 0)
                    # 부모 요소인 label 찾아서 클릭
                    parent_label = self.devtools.driver.find_element("css selector", "label[for='speed']")
                    parent_label.click()
                    time.sleep(1)  # 필터 적용 대기
                    self.progress_signal.emit("스피드 필터 적용 완료", 0)
                    return
            except Exception as e:
                self.progress_signal.emit(f"정확한 선택자로 찾기 실패: {str(e)}", 0)
            
            # 방법 2: 부분 선택자 사용
            try:
                # data-role='typography'와 스피드 텍스트 포함된 요소 찾기
                typography_elements = self.devtools.driver.find_elements("css selector", 
                    "span[data-role='typography']")
                
                for element in typography_elements:
                    if "스피드" in element.text and "슈퍼 스피드" not in element.text:
                        self.progress_signal.emit(f"스피드 라벨 발견: '{element.text}'", 0)
                        # 부모 요소 찾아 올라가기
                        parent = element.find_element("xpath", "./..")
                        if parent.tag_name == "label":
                            parent.click()
                        else:
                            # 부모의 부모 시도
                            grandparent = parent.find_element("xpath", "./..")
                            if grandparent.tag_name == "label":
                                grandparent.click()
                            else:
                                # 직접 클릭
                                element.click()
                        
                        time.sleep(1)  # 필터 적용 대기
                        self.progress_signal.emit("스피드 필터 적용 완료", 0)
                        return
            except Exception as e:
                self.progress_signal.emit(f"부분 선택자로 찾기 실패: {str(e)}", 0)
            
            # 방법 3: 텍스트 기반 XPath 사용
            try:
                # XPath로 '스피드'라는 텍스트를 포함한 요소 찾기
                xpath_expr = "//span[contains(text(), '스피드') and not(contains(text(), '슈퍼 스피드'))]"
                speed_elements = self.devtools.driver.find_elements("xpath", xpath_expr)
                
                if speed_elements:
                    for elem in speed_elements:
                        self.progress_signal.emit(f"XPath로 스피드 텍스트 발견: '{elem.text}'", 0)
                        try:
                            # 부모 요소가 label인지 확인
                            parent = elem.find_element("xpath", "./..")
                            if parent.tag_name == "label":
                                parent.click()
                            else:
                                # 직접 클릭
                                elem.click()
                            
                            time.sleep(1)  # 필터 적용 대기
                            self.progress_signal.emit("스피드 필터 적용 완료", 0)
                            return
                        except:
                            continue
            except Exception as e:
                self.progress_signal.emit(f"XPath로 찾기 실패: {str(e)}", 0)
            
            # 방법 4: 일반적인 방법 (기존 코드)
            filters = self.devtools.driver.find_elements("css selector", "span, label, button, div")
            for item in filters:
                try:
                    text = item.text.lower()
                    if "스피드" in text and "슈퍼 스피드" not in text:
                        self.progress_signal.emit(f"일반 요소에서 스피드 필터 발견: '{item.text}'", 0)
                        item.click()
                        time.sleep(1)  # 필터 적용 대기
                        return
                except:
                    continue
                    
        except Exception as e:
            self.progress_signal.emit(f"스피드 필터 적용 중 오류: {str(e)}", 0)
        
        # 모든 방법 실패 시
        self.progress_signal.emit("스피드 필터를 찾지 못했습니다. 전체 방 목록을 가져옵니다.", 0)
        
    def _find_scroll_container(self):
        """스크롤 컨테이너 찾기 최적화"""
        # 여러 가능한 스크롤 컨테이너 선택자
        selectors = [
            "div.scrollable-container", 
            "div.lobby-games-container",
            "div.games-container",
            "div.game-tiles-container",
            "[data-role='games-container']",
            "div.tile-container",
            ".lobby-content",
            "div.content-scrollable",
            "main"
        ]
        
        for selector in selectors:
            elements = self.devtools.driver.find_elements("css selector", selector)
            if elements:
                self.progress_signal.emit(f"스크롤 컨테이너 발견: '{selector}'", 0)
                return elements[0]
        
        # 최후의 수단으로 body 태그 사용
        self.progress_signal.emit("전용 스크롤 컨테이너를 찾지 못해 body 태그 사용", 0)
        return self.devtools.driver.find_element("css selector", "body")

    def _find_elements_by_multiple_selectors(self, selectors):
        """한 번에 여러 선택자로 요소 검색"""
        all_elements = []
        
        for selector in selectors:
            try:
                elements = self.devtools.driver.find_elements("css selector", selector)
                if elements:
                    all_elements.extend(elements)
            except:
                continue
                
        return all_elements

    def _get_current_visible_rooms(self, elements):
        """현재 화면에 보이는 방 이름 목록 가져오기"""
        rooms = set()
        
        for element in elements:
            try:
                # 요소가 보이는지 확인
                if not element.is_displayed():
                    continue
                    
                # 텍스트 추출 및 정리
                text = clean_text(element.text)
                
                # 빈 텍스트 무시
                if not text:
                    continue
                    
                # 스피드 필터 적용 (filter_type에 따라)
                if self.filter_type == "speed":
                    if "스피드" in text and "슈퍼 스피드" not in text:
                        rooms.add(text)
                else:
                    # 다른 필터 없이 모든 방 추가
                    rooms.add(text)
                    
            except:
                continue
                
        return list(rooms)

    def _scroll_down_enhanced(self, container):
        """개선된 스크롤 다운 메서드"""
        try:
            # 현재 스크롤 위치 확인
            current_scroll = self.devtools.driver.execute_script("return arguments[0].scrollTop", container)
            
            # 스크롤 높이 확인
            scroll_height = self.devtools.driver.execute_script("return arguments[0].scrollHeight", container)
            
            # 방법 1: 특정 픽셀만큼 스크롤
            new_scroll = current_scroll + 500  # 500픽셀 더 내림
            self.devtools.driver.execute_script("arguments[0].scrollTop = arguments[1]", container, new_scroll)
            
            # 방법 2: 특정 요소까지 스크롤 (마지막 방 요소를 찾아서)
            elements = self._find_elements_by_multiple_selectors([".tile--5d2e6", ".game-tile"])
            if elements:
                last_visible = None
                for elem in reversed(elements):
                    try:
                        if elem.is_displayed():
                            last_visible = elem
                            break
                    except:
                        continue
                
                if last_visible:
                    self.devtools.driver.execute_script("arguments[0].scrollIntoView(false)", last_visible)
            
            # 로그 추가
            self.progress_signal.emit(f"스크롤: {current_scroll} → {new_scroll} (총 높이: {scroll_height})", 0)
            
        except Exception as e:
            # 실패 시 기본 스크롤 방식 시도
            try:
                self.devtools.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", container)
            except:
                # 최후의 수단: 창 스크롤
                self.devtools.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    def _filter_rooms(self, all_rooms):
        """필터링 최적화 (리스트 컴프리헨션 사용)"""
        if self.filter_type == "speed":
            return [room for room in all_rooms if "스피드" in room and "슈퍼 스피드" not in room]
        return all_rooms