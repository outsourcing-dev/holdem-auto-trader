from PyQt6.QtWidgets import QTableWidgetItem
import re

def clean_text(text):
    """숨겨진 특수 문자 제거"""
    text = re.sub(r'[\u200c\u2066\u2069]', '', text)  # 보이지 않는 문자 삭제
    return text.strip()

class RoomManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.devtools = main_window.devtools
    
    def get_all_rooms(self):
        """iframe 내에서 처음 보이는 30개의 방 정보만 가져오기"""
        try:
            # iframe으로 전환
            iframe = self.devtools.driver.find_element("css selector", "iframe")
            self.devtools.driver.switch_to.frame(iframe)

            print("[INFO] iframe 내부 콘텐츠 로드 대기...")
            import time
            time.sleep(3)

            all_rooms = set()

            # ✅ 특정 클래스(tile--5d2e6) 방 이름 요소 찾기
            name_elements = self.devtools.driver.find_elements("css selector", ".tile--5d2e6")
            print(f"[INFO] 현재 보이는 방 개수: {len(name_elements)}")

            for idx, element in enumerate(name_elements):
                try:
                    full_text = element.text.strip()
                    clean_full_text = clean_text(full_text)  # ✅ 숨겨진 문자 제거
                    lines = [line.strip() for line in clean_full_text.splitlines() if line.strip()]

                    if lines:
                        room_name = clean_text(lines[0])  # ✅ 첫 번째 줄(방 이름)만 추출 후 클리닝

                        print(f"[DEBUG] room[{idx}] 원본 데이터: {repr(full_text)}")  
                        print(f"[DEBUG] room[{idx}] 첫 줄 (클린): {repr(room_name)}")  

                        if room_name:
                            all_rooms.add(room_name)
                    else:
                        print(f"[WARNING] room[{idx}] 비어있는 값 감지! -> {repr(full_text)}")

                except Exception as e:
                    print(f"[ERROR] 방 이름 가져오는 중 오류 발생: {e}")

            final_rooms = list(all_rooms)
            print(f"[INFO] 최종적으로 찾은 방 개수: {len(final_rooms)}")

            return final_rooms

        except Exception as e:
            print(f"[ERROR] get_all_rooms 실행 중 오류 발생: {e}")
            return []
    
    def load_rooms_into_table(self, rooms=None):
        """방 목록을 테이블에 업데이트"""
        print("[DEBUG] load_rooms_into_table() 실행됨")

        # rooms가 None이면 전체 방 목록 조회
        if rooms is None:
            rooms = self.get_all_rooms()

        if not rooms:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self.main_window, "알림", "방 목록을 불러올 수 없습니다.")
            return

        self.main_window.room_table.setRowCount(len(rooms))  # 테이블 행 개수 설정

        for row, room in enumerate(rooms):
            self.main_window.room_table.setItem(row, 0, QTableWidgetItem(room))