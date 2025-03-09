# utils/room_manager.py 수정

import json
import os
from PyQt6.QtWidgets import (QTableWidgetItem, QCheckBox, QMessageBox, QLabel,
                           QProgressBar, QHeaderView, QWidget, QHBoxLayout)
from PyQt6.QtCore import Qt, QTimer
import time
import re
import random

# RoomLoaderThread 클래스 import
from utils.room_loader import RoomLoaderThread

ROOM_DATA_FILE = "room_settings.json"

def clean_text(text):
    """숨겨진 특수 문자 제거"""
    text = re.sub(r'[\u200c\u2066\u2069]', '', text)  # 보이지 않는 문자 삭제
    return text.strip()

class RoomManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.devtools = main_window.devtools
        self.rooms_data = []  # 방 데이터를 저장할 리스트 ([{"name": "방이름", "checked": True}, ...])
        self.room_visit_queue = []  # 방문할 방들의 순서 (랜덤하게 섞인 배열)
        self.load_room_settings()  # 저장된 방 설정 불러오기
        
        # 로딩 메시지 박스 참조 (자동 닫기용)
        self.loading_msgbox = None
        
        # 로딩 스레드
        self.room_loader_thread = None

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

    def show_loading_msgbox(self, message):
        """로딩 메시지 박스 표시 (멀티 스레딩 작업이 완료될 때까지 유지)"""
        self.loading_msgbox = QMessageBox(self.main_window)
        self.loading_msgbox.setWindowTitle("알림")
        self.loading_msgbox.setText(message)
        self.loading_msgbox.setStandardButtons(QMessageBox.StandardButton.NoButton)  # 버튼 없음
        
        # 진행 상태 표시 추가
        progress_bar = QProgressBar(self.loading_msgbox)
        progress_bar.setRange(0, 0)  # 무한 진행 표시
        progress_bar.setFixedHeight(15)
        progress_bar.setTextVisible(False)
        self.loading_msgbox.layout().addWidget(progress_bar, 1, 0)
        
        # 논블로킹 모드로 표시
        self.loading_msgbox.show()
    
    def merge_room_data(self, new_room_names, reset_existing=False):
        """
        새로 가져온 방 목록과 기존 저장된 방 목록을 병합합니다.
        
        Args:
            new_room_names (list): 새로 가져온 방 이름 목록 (dict 또는 str 형식)
            reset_existing (bool): True일 경우 기존 방 목록을 초기화하고 새 목록으로 교체
        """
        if reset_existing:
            # 입력이 dict 형식인지 str 형식인지 확인
            self.rooms_data = []
            
            if new_room_names and isinstance(new_room_names[0], dict):
                # dict 형식이면 그대로 사용
                self.rooms_data = new_room_names
            else:
                # str 형식이면 dict로 변환 (모든 방의 체크 상태를 True로 설정)
                for name in new_room_names:
                    self.rooms_data.append({"name": name, "checked": True})
                    
            print(f"[INFO] 방 목록을 모두 초기화하고 새로운 {len(self.rooms_data)}개 방으로 교체했습니다. (모두 선택됨)")
        else:
            # 기존 방식대로 병합
            existing_names = {room["name"] for room in self.rooms_data}
            
            # 새로운 방 추가
            if new_room_names and isinstance(new_room_names[0], dict):
                # dict 형식이면 name 추출
                for room_data in new_room_names:
                    name = room_data["name"]
                    if name not in existing_names:
                        self.rooms_data.append(room_data)
                        existing_names.add(name)
            else:
                # str 형식이면 dict로 변환
                for name in new_room_names:
                    if name not in existing_names:
                        self.rooms_data.append({"name": name, "checked": False})
                        existing_names.add(name)

    def show_room_list_dialog(self):
        """
        방 목록 불러오기 다이얼로그 표시
        - 기존 방 불러오기 또는 새로운 방 불러오기 선택 가능
        """
        # 1. 기존 저장된 방 목록을 불러올지 묻기
        reply = QMessageBox.question(
            self.main_window,
            "방 목록 불러오기",
            "기존 저장된 방 목록을 불러오시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 저장된 JSON 파일에서 불러오기
            print("[INFO] 저장된 방 목록 불러오기 선택")
            self.load_room_settings()
            self.load_rooms_into_table(self.rooms_data)
            return
        
        # 2. 새로운 방 목록을 불러올지 묻기
        reply = QMessageBox.question(
            self.main_window,
            "방 목록 불러오기",
            "현재 사이트의 '스피드' 방을 모두 불러와서 저장하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 카지노 창으로 전환
            if not self.main_window.switch_to_casino_window():
                QMessageBox.warning(self.main_window, "오류", "카지노 창을 찾을 수 없습니다.")
                return
                
            # 2.5초 후 자동으로 닫히는 로딩 메시지 표시
            # self.show_loading_msgbox("스피드 방 목록을 불러옵니다. 잠시만 기다려주세요.")
            
            # 스피드 방 목록 로딩 스레드 생성 및 시작
            self.start_room_loader_thread()
                
            # 카지노 로비 창으로 포커싱 확실히 유지
            self.main_window.switch_to_casino_window()
    
    # RoomManager 클래스의 update_loading_progress 함수 수정
    def update_loading_progress(self, message, count):
        """방 로딩 진행 상황 업데이트 (로그만 남기고 UI에는 표시 안 함)"""
        # 로그에만 기록
        print(f"[INFO] 방 목록 불러오는 중: {message} (발견 방: {count}개)")

    # RoomManager 클래스의 on_room_loading_finished 함수 수정

    def on_room_loading_finished(self, rooms_data):
        """방 로딩 완료 시 호출되는 콜백"""
        if self.loading_msgbox:  
            self.loading_msgbox.accept()  # 로딩 메시지 박스 닫기
            self.loading_msgbox = None  # 변수 초기화

        # 로딩 결과가 있는 경우
        if rooms_data:
            self.merge_room_data(rooms_data, reset_existing=True)
            self.load_rooms_into_table(self.rooms_data)
            
            save_result = self.save_room_settings()
            
            if save_result:
                print(f"[INFO] 총 {len(self.rooms_data)}개의 스피드 방 목록을 불러와 저장했습니다.")
                
                # 성공 메시지
                QMessageBox.information(
                    self.main_window,
                    "방 목록 저장 완료",
                    f"총 {len(self.rooms_data)}개의 방 목록을 불러와 저장했습니다."
                )
            else:
                print("[ERROR] 방 목록 저장 실패")
                QMessageBox.warning(self.main_window, "저장 실패", "방 목록을 저장하는 데 실패했습니다.")
        else:
            print("[ERROR] 방 목록을 불러오지 못했습니다.")
            QMessageBox.warning(self.main_window, "오류", "방 목록을 불러오는 데 실패했습니다.")


    # RoomManager 클래스의 start_room_loader_thread 함수 수정

    def start_room_loader_thread(self):
        """방 목록 로딩 스레드 시작"""
        if self.room_loader_thread and self.room_loader_thread.isRunning():
            self.room_loader_thread.stop()
            self.room_loader_thread.wait()

        self.room_loader_thread = RoomLoaderThread(self.devtools, "speed")
        
        # 시그널 연결
        self.room_loader_thread.progress_signal.connect(self.update_loading_progress)
        self.room_loader_thread.finished_signal.connect(self.on_room_loading_finished)

        # 로딩 메시지 박스 표시 (이제 스레드가 끝날 때까지 유지됨)
        self.show_loading_msgbox("스피드 방 목록을 불러옵니다. 잠시만 기다려주세요.")

        self.room_loader_thread.start()
        print("[INFO] 방 목록 로딩 스레드 시작됨")
        
    def get_all_rooms(self):
        """iframe 내에서 방 정보 가져오기 (기존 기능, 수정 없음)"""
        print("[DEBUG] get_all_rooms() 메서드 시작")

        try:
            # iframe으로 전환
            iframe = self.devtools.driver.find_element("css selector", "iframe")
            self.devtools.driver.switch_to.frame(iframe)

            print("[INFO] iframe 내부 콘텐츠 로드 대기...")
            time.sleep(1)

            all_rooms = set()

            # 특정 클래스(tile--5d2e6) 방 이름 요소 찾기
            name_elements = self.devtools.driver.find_elements("css selector", ".tile--5d2e6")
            print(f"[INFO] 현재 보이는 방 개수: {len(name_elements)}")

            for idx, element in enumerate(name_elements):
                try:
                    full_text = element.text.strip()
                    clean_full_text = clean_text(full_text)  # 숨겨진 문자 제거
                    lines = [line.strip() for line in clean_full_text.splitlines() if line.strip()]

                    if lines:
                        room_name = clean_text(lines[0])  # 첫 번째 줄(방 이름)만 추출 후 클리닝

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
        
        # 테이블 스타일 설정 - 전체 배경을 흰색으로 설정
        room_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #DDDDDD;
                border: 1px solid #CCCCCC;
            }
            QTableWidget::item {
                background-color: white;
                padding: 4px;
                text-align: center;
            }
            QTableWidget QHeaderView::section {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 4px;
                border: 1px solid #2E7D32;
                text-align: center;
            }
            QCheckBox {
                background-color: white;
            }
        """)
        
        # 테이블 설정
        room_table.setColumnCount(2)  # 체크박스, 방 이름
        room_table.setHorizontalHeaderLabels(["선택", "방 이름"])
        
        # 조정 가능한 너비 대신 비율 설정 (전체 너비에 맞추기)
        room_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        room_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        # 체크박스 열 너비 설정
        room_table.setColumnWidth(0, 50)  # 체크박스 열 너비
        
        # 테이블 행 개수 설정
        room_table.setRowCount(len(rooms_data))
        
        # 체크박스와 방 이름 설정
        for row, room_data in enumerate(rooms_data):
            # 체크박스 생성 (centralized using a widget)
            checkbox_container = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_container)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)  # 여백 제거
            
            checkbox = QCheckBox()
            checkbox.setChecked(room_data["checked"])
            checkbox.stateChanged.connect(lambda state, r=row: self.on_checkbox_changed(r, state))
            
            # 체크박스 스타일 설정 - 배경을 흰색으로
            checkbox.setStyleSheet("QCheckBox { background-color: white; }")
            
            checkbox_layout.addWidget(checkbox)
            
            # 체크박스를 테이블 중앙에 배치
            self.main_window.room_table.setCellWidget(row, 0, checkbox_container)
            
            # 방 이름 설정 - 중앙 정렬
            name_item = QTableWidgetItem(room_data["name"])
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)  # 중앙 정렬
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