import json
import os
from PyQt6.QtWidgets import QTableWidgetItem, QCheckBox, QMessageBox
from PyQt6.QtCore import Qt
import time
import re
import random

ROOM_DATA_FILE = "room_settings.json"

def clean_text(text):
    """숨겨진 특수 문자 제거"""
    text = re.sub(r'[\u200c\u2066\u2069]', '', text)  # 보이지 않는 문자 삭제
    return text.strip()

class RoomManager:
    # utils/room_manager.py의 RoomManager 클래스에 추가
    def __init__(self, main_window):
        self.main_window = main_window
        self.devtools = main_window.devtools
        self.rooms_data = []  # 방 데이터를 저장할 리스트 ([{"name": "방이름", "checked": True}, ...])
        self.room_visit_queue = []  # 방문할 방들의 순서 (랜덤하게 섞인 배열)
        self.load_room_settings()  # 저장된 방 설정 불러오기

    def generate_visit_order(self):
        """
        체크된 방들의 방문 순서를 랜덤하게 생성합니다.
        """
        checked_rooms = self.get_checked_rooms()
        if not checked_rooms:
            return False
            
        # 방 이름만 추출
        room_names = [room['name'] for room in checked_rooms]
        
        # 랜덤하게 순서 섞기
        random.shuffle(room_names)
        
        self.room_visit_queue = room_names
        # 로깅 방식 변경 - logger 대신 print 사용
        print(f"[INFO] 새로운 방문 순서 생성: {self.room_visit_queue}")
        return True

    def get_next_room_to_visit(self):
        """
        다음에 방문할 방을 큐에서 가져옵니다.
        큐가 비어있으면 새로운 방문 순서를 생성합니다.
        
        Returns:
            str: 다음 방문할 방 이름 또는 None
        """
        # 큐가 비어있으면 새로 생성
        if not self.room_visit_queue:
            success = self.generate_visit_order()
            if not success:
                return None
        
        # 큐에서 첫 번째 방 이름 가져오기
        if self.room_visit_queue:
            room_name = self.room_visit_queue.pop(0)
            print(f"[INFO] 다음 방문 방: {room_name} (남은 방: {len(self.room_visit_queue)}개)")
            return room_name
        
        return None

    def mark_current_room_visited(self, room_name):
        """
        현재 방을 방문 처리합니다.
        방이 큐에 있을 경우 제거합니다.
        
        Args:
            room_name (str): 방문 처리할 방 이름
        """
        # 혹시 이 방이 아직 큐에 있다면 제거
        if room_name in self.room_visit_queue:
            self.room_visit_queue.remove(room_name)
            # 로깅 방식 변경
            print(f"[INFO] '{room_name}'을 방문 큐에서 제거 (남은 방: {len(self.room_visit_queue)}개)")

    def get_all_rooms(self):
        """iframe 내에서 방 정보 가져오기"""
        print("[DEBUG] get_all_rooms() 메서드 시작")

        try:
            # iframe으로 전환
            iframe = self.devtools.driver.find_element("css selector", "iframe")
            self.devtools.driver.switch_to.frame(iframe)

            print("[INFO] iframe 내부 콘텐츠 로드 대기...")
            time.sleep(1)

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

            # iframe에서 나오기
            self.devtools.driver.switch_to.default_content()
            
            # 기존 방 설정과 새로 가져온 방 목록을 병합
            self.merge_room_data(list(all_rooms))

            print(f"[INFO] 최종적으로 찾은 방 개수: {len(self.rooms_data)}")
            return self.rooms_data

        except Exception as e:
            print(f"[ERROR] get_all_rooms 실행 중 오류 발생: {e}")
            # iframe에서 나오기 시도
            try:
                self.devtools.driver.switch_to.default_content()
            except:
                pass
            return []
    
    def merge_room_data(self, new_room_names):
        """새로 가져온 방 목록과 기존 저장된 방 목록을 병합"""
        # 새로운 방은 기본적으로 체크 해제 상태로 추가
        existing_names = {room["name"] for room in self.rooms_data}
        
        # 새로운 방 추가
        for name in new_room_names:
            if name not in existing_names:
                self.rooms_data.append({"name": name, "checked": False})
                existing_names.add(name)
    
    # utils/room_manager.py에 메서드 추가
    def load_rooms_into_table(self, rooms_data=None):
        """방 목록을 테이블에 업데이트"""
        print("[DEBUG] load_rooms_into_table() 실행됨")
        print(f"[DEBUG] 매개변수 rooms_data 타입: {type(rooms_data)}, 값: {rooms_data}")

        # 1. rooms_data가 None이면 저장된 데이터 사용
        if rooms_data is None:
            print("[DEBUG] rooms_data가 None, 저장된 데이터 사용")
            rooms_data = self.rooms_data
            print(f"[DEBUG] 저장된 self.rooms_data 타입: {type(self.rooms_data)}, 길이: {len(self.rooms_data)}")
        
        # 2. 데이터가 비어있는지 확인 (빈 리스트면 get_all_rooms 호출)
        if isinstance(rooms_data, list) and len(rooms_data) == 0:
            print("[DEBUG] rooms_data가 빈 리스트, get_all_rooms() 호출")
            QMessageBox.information(self.main_window, "알림", "방 목록을 불러옵니다.")
            try:
                rooms_data = self.get_all_rooms()
                print(f"[DEBUG] get_all_rooms() 결과 타입: {type(rooms_data)}, 개수: {len(rooms_data) if rooms_data else 0}")
            except Exception as e:
                print(f"[ERROR] get_all_rooms() 호출 중 예외 발생: {e}")
                import traceback
                traceback.print_exc()

        # 3. 최종 데이터 확인
        if not rooms_data or (isinstance(rooms_data, list) and len(rooms_data) == 0):
            print("[DEBUG] 최종 rooms_data가 비어있음")
            QMessageBox.warning(self.main_window, "알림", "방 목록을 불러올 수 없습니다.")
            return

        # 테이블 설정 업데이트 (체크박스 열 추가)
        room_table = self.main_window.room_table
        room_table.setColumnCount(2)  # 체크박스, 방 이름
        room_table.setHorizontalHeaderLabels(["선택", "방 이름"])
        room_table.setColumnWidth(0, 50)  # 체크박스 열 너비
        room_table.setColumnWidth(1, 200)  # 방 이름 열 너비
        
        # 테이블 행 개수 설정
        room_table.setRowCount(len(rooms_data))
        
        # 체크박스와 방 이름 설정
        for row, room_data in enumerate(rooms_data):
            # 체크박스 생성 (centralized using a widget)
            checkbox = QCheckBox()
            checkbox.setChecked(room_data["checked"])
            checkbox.stateChanged.connect(lambda state, r=row: self.on_checkbox_changed(r, state))
            
            # 체크박스를 테이블 중앙에 배치
            self.main_window.room_table.setCellWidget(row, 0, checkbox)
            
            # 방 이름 설정
            name_item = QTableWidgetItem(room_data["name"])
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # 편집 불가능하게 설정
            room_table.setItem(row, 1, name_item)
        
        # 방 목록이 성공적으로 로드되면 버튼 활성화
        print("[DEBUG] 방 목록 로드 완료, 버튼 활성화")
        self.main_window.start_button.setEnabled(True)
        self.main_window.stop_button.setEnabled(True)
        
    def on_checkbox_changed(self, row, state):
        """체크박스 상태가 변경되었을 때 호출"""
        if 0 <= row < len(self.rooms_data):
            self.rooms_data[row]["checked"] = bool(state)
            print(f"[DEBUG] 방 '{self.rooms_data[row]['name']}' 체크 상태 변경: {bool(state)}")
    
    def save_room_settings(self):
        """방 설정을 JSON 파일로 저장"""
        try:
            with open(ROOM_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.rooms_data, f, ensure_ascii=False, indent=4)
            print(f"[INFO] 방 설정 저장 완료: {len(self.rooms_data)}개 방")
            return True
        except Exception as e:
            print(f"[ERROR] 방 설정 저장 중 오류 발생: {e}")
            return False
    
    def load_room_settings(self):
        """저장된 방 설정을 JSON 파일에서 불러오기"""
        if not os.path.exists(ROOM_DATA_FILE):
            print("[INFO] 저장된 방 설정 파일이 없습니다.")
            return
            
        try:
            with open(ROOM_DATA_FILE, "r", encoding="utf-8") as f:
                self.rooms_data = json.load(f)
            print(f"[INFO] 방 설정 불러오기 완료: {len(self.rooms_data)}개 방")
        except Exception as e:
            print(f"[ERROR] 방 설정 불러오기 중 오류 발생: {e}")
            self.rooms_data = []
    
    def get_checked_rooms(self):
        """체크된 방 목록 반환"""
        return [room for room in self.rooms_data if room["checked"]]