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
        
        try:
            self.progress_signal.emit("방 목록을 불러오는 중...", 0)
            self.devtools.driver.switch_to.default_content()
            time.sleep(1)

            # iframe 존재 여부 확인 후 전환 (최적화)
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
            
            self.progress_signal.emit("스크롤 컨테이너 찾는 중...", 0)
            scroll_container = self._find_scroll_container()

            # 여러 선택자로 방 찾기
            selectors = [".tile--5d2e6", ".game-tile", "[data-role='game-tile']", "[class*='tile']", "div.lobby-table__game"]
            room_elements = self._find_elements_by_multiple_selectors(selectors)
            initial_rooms = len(room_elements)

            self.progress_signal.emit(f"초기 방 개수: {initial_rooms}개", initial_rooms)
            
            max_scroll_attempts = 10
            no_new_rooms_count = 0
            scroll_attempts = 0

            while scroll_attempts < max_scroll_attempts and no_new_rooms_count < 2:
                if self.stop_requested:
                    self.progress_signal.emit("사용자에 의해 중단됨", len(all_rooms))
                    break

                # 현재 보이는 방 목록 수집
                visible_rooms = self._get_current_visible_rooms(room_elements)
                new_rooms = [room for room in visible_rooms if room not in all_rooms]
                
                if new_rooms:
                    for room in new_rooms:
                        all_rooms.append(room)
                        self.found_room_signal.emit(room)
                    self.progress_signal.emit(f"발견된 방: {len(all_rooms)}개", len(all_rooms))
                    no_new_rooms_count = 0
                else:
                    no_new_rooms_count += 1
                
                # 스크롤 시도
                self._scroll_down(scroll_container)
                time.sleep(2)  # 대기 시간 단축
                scroll_attempts += 1

            filtered_rooms = self._filter_rooms(all_rooms)
            result_rooms = [{"name": room, "checked": True} for room in filtered_rooms]
            self.finished_signal.emit(result_rooms)

        except Exception as e:
            self.progress_signal.emit(f"오류 발생: {str(e)}", len(all_rooms))
            self.finished_signal.emit([])

    def _apply_speed_filter(self):
        """스피드 필터 적용 최적화"""
        self.progress_signal.emit("스피드 필터 적용 중...", 0)
        try:
            filters = self.devtools.driver.find_elements("css selector", "span, label, button, div")
            for item in filters:
                if "스피드" in item.text and "슈퍼 스피드" not in item.text:
                    item.click()
                    time.sleep(1)  
                    return
        except:
            pass
        self.progress_signal.emit("스피드 필터를 찾지 못함", 0)

    def _find_scroll_container(self):
        """스크롤 컨테이너 찾기 최적화"""
        for selector in ["div.scrollable-container", "main", "body"]:
            container = self.devtools.driver.find_elements("css selector", selector)
            if container:
                return container[0]
        return self.devtools.driver.find_element("css selector", "body")

    def _find_elements_by_multiple_selectors(self, selectors):
        """한 번에 여러 선택자로 요소 검색"""
        for selector in selectors:
            elements = self.devtools.driver.find_elements("css selector", selector)
            if elements:
                return elements
        return []

    def _get_current_visible_rooms(self, elements):
        """현재 화면에 보이는 방 이름 목록 가져오기"""
        rooms = set()
        for element in elements:
            try:
                text = clean_text(element.text)
                if "스피드" in text and text not in rooms:
                    rooms.add(text)
            except:
                pass
        return list(rooms)

    def _scroll_down(self, container):
        """스크롤 내리기"""
        try:
            self.devtools.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", container)
        except:
            self.devtools.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    def _filter_rooms(self, all_rooms):
        """필터링 최적화 (리스트 컴프리헨션 사용)"""
        if self.filter_type == "speed":
            return [room for room in all_rooms if "스피드" in room and "슈퍼 스피드" not in room]
        return all_rooms
