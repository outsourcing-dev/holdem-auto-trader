# utils/room_loader.py에 추가

from PyQt6.QtCore import QThread, pyqtSignal
import time
import re
import urllib3

def clean_text(text):
    """숨겨진 특수 문자 제거"""
    text = re.sub(r'[\u200c\u2066\u2069]', '', text)  # 보이지 않는 문자 삭제
    return text.strip()

class RoomLoaderThread(QThread):
    progress_signal = pyqtSignal(str, int)  # 메시지, 발견된 방 개수
    found_room_signal = pyqtSignal(str)  # 새로 발견된 방 이름
    finished_signal = pyqtSignal(list)  # 최종 방 목록 [{"name": 방이름, "checked": True}, ...]

    def __init__(self, devtools, filter_type="speed"):
        super().__init__()
        self.devtools = devtools
        self.filter_type = filter_type  # "speed", "all" 등
        self.stop_requested = False
        
    def run(self):
        all_rooms = []
        
        try:
            # 디버깅: 현재 페이지 정보 로깅
            self.progress_signal.emit("디버깅 정보 수집 중...", 0)
            current_url = self.devtools.driver.current_url
            page_title = self.devtools.driver.title
            
            with open("page_debug.log", "w", encoding="utf-8") as f:
                f.write(f"현재 URL: {current_url}\n")
                f.write(f"페이지 제목: {page_title}\n\n")
                
                # iframe 정보 확인
                iframes = self.devtools.driver.find_elements("css selector", "iframe")
                f.write(f"iframe 개수: {len(iframes)}\n")
                
                for i, frame in enumerate(iframes):
                    f.write(f"iframe #{i+1} id: {frame.get_attribute('id')}, name: {frame.get_attribute('name')}\n")
                
                # 페이지 구조 확인
                f.write("\n==== 페이지 HTML ====\n")
                f.write(self.devtools.driver.page_source[:10000])  # 처음 10000자만 저장
                
            self.progress_signal.emit("디버깅 정보 page_debug.log 파일에 저장됨", 0)
             # iframe으로 전환
            self.progress_signal.emit("iframe으로 전환 중...", 0)
            
            # iframe으로 전환한 후 iframe 내부 구조 로깅 (두 번째 로깅 코드)
            if len(iframes) > 0:
                iframe = iframes[0]
                self.devtools.driver.switch_to.frame(iframe)
                time.sleep(2)  # 로드 대기 시간 증가
                
                with open("iframe_debug.log", "w", encoding="utf-8") as f:
                    f.write("==== iframe 내부 HTML ====\n")
                    f.write(self.devtools.driver.page_source[:10000])
                    
                    # 방 목록 요소 찾기 시도
                    tile_selectors = [".tile--5d2e6", ".game-tile", "[data-role='game-tile']", "[class*='tile']"]
                    for selector in tile_selectors:
                        elements = self.devtools.driver.find_elements("css selector", selector)
                        f.write(f"\n선택자 '{selector}'로 찾은 요소 개수: {len(elements)}\n")
                        
                        # 첫 번째 요소의 HTML 구조 확인
                        if elements:
                            f.write(f"첫 번째 요소 HTML: {elements[0].get_attribute('outerHTML')}\n")
                            
                self.progress_signal.emit("iframe 내부 디버깅 정보 iframe_debug.log 파일에 저장됨", 0)

            # 필터 유형에 따른 처리
            if self.filter_type == "speed":
                self._apply_speed_filter()
            
            # 스크롤 컨테이너 찾기
            self.progress_signal.emit("스크롤 컨테이너 찾는 중...", 0)
            scroll_container = self._find_scroll_container()
            
            # 초기 방 개수 체크
            initial_rooms = len(self.devtools.driver.find_elements("css selector", ".tile--5d2e6"))
            self.progress_signal.emit(f"초기 방 개수: {initial_rooms}개", initial_rooms)
            
            # 스크롤하면서 방 목록 수집
            max_scroll_attempts = 20
            scroll_attempts = 0
            current_rooms_count = 0
            no_new_rooms_count = 0  # 새 방이 발견되지 않은 연속 횟수
            
            while scroll_attempts < max_scroll_attempts and no_new_rooms_count < 3:
                if self.stop_requested:
                    self.progress_signal.emit("사용자에 의해 중단됨", len(all_rooms))
                    break
                
                # 현재 방 개수 저장
                current_rooms = len(self.devtools.driver.find_elements("css selector", ".tile--5d2e6"))
                
                # 스크롤 방법 1: 스크롤 컨테이너까지 스크롤
                self.devtools.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)
                
                # 스크롤 방법 2: 전체 페이지 스크롤
                self.devtools.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # 스크롤 방법 3: 가장 아래 요소로 스크롤
                room_elements = self.devtools.driver.find_elements("css selector", ".tile--5d2e6")
                if room_elements:
                    last_element = room_elements[-1]
                    self.devtools.driver.execute_script("arguments[0].scrollIntoView(true);", last_element)
                
                self.progress_signal.emit(f"스크롤 진행 중... ({scroll_attempts+1}/{max_scroll_attempts})", current_rooms)
                time.sleep(3)  # 로딩 대기 시간
                
                # 새로운 방 개수 확인
                new_rooms = len(self.devtools.driver.find_elements("css selector", ".tile--5d2e6"))
                
                # 현재 보이는 방 가져오기
                visible_rooms = self._get_current_visible_rooms()
                
                # 새로 발견된 방만 추가
                for room in visible_rooms:
                    if room not in all_rooms:
                        all_rooms.append(room)
                        self.found_room_signal.emit(room)
                
                # 갱신된 전체 방 개수
                self.progress_signal.emit(f"발견된 방: {len(all_rooms)}개", len(all_rooms))
                
                # 개수가 증가하지 않으면 추가 시도
                if new_rooms <= current_rooms:
                    no_new_rooms_count += 1
                    self.progress_signal.emit(f"새 방이 발견되지 않음 ({no_new_rooms_count}/3)", len(all_rooms))
                    
                    # 추가 스크롤 방식 시도
                    self._try_additional_scroll_methods(scroll_container)
                    time.sleep(3)  # 추가 대기
                else:
                    no_new_rooms_count = 0  # 새 방이 발견되면 카운터 리셋
                
                scroll_attempts += 1
            
            # 필터링 조건에 맞는 최종 방 목록 생성
            filtered_rooms = self._filter_rooms(all_rooms)
            
            # iframe에서 나오기
            self.devtools.driver.switch_to.default_content()
            
            # 최종 결과 반환 (각 방에 대해 {"name": 방이름, "checked": True} 형태로)
            result_rooms = [{"name": room, "checked": True} for room in filtered_rooms]
            self.finished_signal.emit(result_rooms)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.progress_signal.emit(f"오류 발생: {str(e)}", len(all_rooms))
            
            # iframe에서 나오기 시도
            try:
                self.devtools.driver.switch_to.default_content()
            except:
                pass
                
            self.finished_signal.emit([])  # 빈 목록 전달
    
    def _apply_speed_filter(self):
        """스피드 필터 적용"""
        self.progress_signal.emit("스피드 필터 찾는 중...", 0)
        speed_filter = None
        
        try:
            # 스피드 필터 찾기 (해당 텍스트를 포함한 span 요소)
            speed_spans = self.devtools.driver.find_elements("css selector", "span.Typography--d2c9a.FilterItemText--e9fbf")
            for span in speed_spans:
                if "스피드" in span.text and "슈퍼 스피드" not in span.text:
                    speed_filter = span
                    break
            
            if not speed_filter:
                # 대체 방법: 모든 필터 요소 중에서 텍스트로 찾기
                filter_elements = self.devtools.driver.find_elements("css selector", "[data-role='filter-item']")
                for element in filter_elements:
                    if "스피드" in element.text and "슈퍼 스피드" not in element.text:
                        speed_filter = element
                        break
        except Exception as e:
            self.progress_signal.emit(f"스피드 필터 찾는 중 오류: {e}", 0)
        
        # 스피드 필터 클릭
        if speed_filter:
            self.progress_signal.emit("스피드 필터 클릭 중...", 0)
            speed_filter.click()
            time.sleep(2)  # 필터 적용 대기
        else:
            self.progress_signal.emit("스피드 필터를 찾을 수 없어 필터 없이 진행합니다", 0)
    
    def _find_scroll_container(self):
        """스크롤 컨테이너 찾기"""
        # 주요 스크롤 컨테이너 선택자들
        possible_scroll_containers = [
            "div.ScrollContainer--aa02a",
            "div[data-role='scroll-container']",
            "div.lobby-games-container",
            "div.games-list",
            "div.scrollable-container",
            "main",
            "body"
        ]
        
        for selector in possible_scroll_containers:
            try:
                containers = self.devtools.driver.find_elements("css selector", selector)
                if containers:
                    self.progress_signal.emit(f"스크롤 컨테이너 찾음: {selector}", 0)
                    return containers[0]
            except Exception:
                pass
        
        self.progress_signal.emit("스크롤 컨테이너를 찾을 수 없어 body를 사용합니다", 0)
        return self.devtools.driver.find_element("css selector", "body")
    
    def _try_additional_scroll_methods(self, scroll_container):
        """추가 스크롤 방식 시도"""
        try:
            # 방법 1: 스크롤 이벤트 직접 트리거
            self.devtools.driver.execute_script("""
                var scrollEvent = new Event('scroll');
                document.dispatchEvent(scrollEvent);
                if (arguments[0]) {
                    arguments[0].dispatchEvent(scrollEvent);
                }
            """, scroll_container)
            
            # 방법 2: 키보드 End 키 시뮬레이션
            try:
                from selenium.webdriver.common.keys import Keys
                from selenium.webdriver.common.action_chains import ActionChains
                
                actions = ActionChains(self.devtools.driver)
                actions.send_keys(Keys.END)
                actions.perform()
            except Exception:
                pass
                
        except Exception as e:
            self.progress_signal.emit(f"추가 스크롤 시도 중 오류: {e}", 0)
    
    def _get_current_visible_rooms(self):
        """현재 보이는 방 목록 가져오기"""
        visible_rooms = []
        
        # 방 이름 요소 찾기
        name_elements = self.devtools.driver.find_elements("css selector", ".tile--5d2e6")
        
        for element in name_elements:
            try:
                full_text = element.text.strip()
                clean_full_text = clean_text(full_text)
                lines = [line.strip() for line in clean_full_text.splitlines() if line.strip()]
                
                if lines:
                    room_name = clean_text(lines[0])
                    if room_name and room_name not in visible_rooms:
                        visible_rooms.append(room_name)
            except Exception:
                continue
                
        return visible_rooms
    
    def _filter_rooms(self, all_rooms):
        """방 필터링 (스피드 필터인 경우)"""
        if self.filter_type == "speed":
            # 스피드 필터 조건:
            # 1. "스피드"가 포함되어야 함
            # 2. "슈퍼 스피드"가 포함되면 안됨
            filtered_rooms = []
            filtered_out = []
            
            for room_name in all_rooms:
                if "스피드" in room_name:
                    if "슈퍼 스피드" not in room_name:
                        filtered_rooms.append(room_name)
                    else:
                        filtered_out.append(room_name)
                else:
                    filtered_out.append(room_name)
            
            self.progress_signal.emit(
                f"필터링 완료: 총 {len(all_rooms)}개 중 {len(filtered_rooms)}개 스피드 방 발견", 
                len(filtered_rooms)
            )
            return filtered_rooms
        
        # 필터 없음 (모든 방 반환)
        return all_rooms
    
    def stop(self):
        """작업 중단 요청"""
        self.stop_requested = True
        self.progress_signal.emit("중단 요청됨...", 0)