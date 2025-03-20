# utils/settings_manager.py에 추가할 수정 코드
import json
import os
import sys

# 기존 상수 정의 대신 함수 사용
def get_settings_file_path():
    """실행 환경에 따라 적절한 settings.json 파일 경로 반환"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 빌드된 실행 파일인 경우
        base_dir = os.path.dirname(sys.executable)
        return os.path.join(base_dir, 'settings.json')
    else:
        # 일반 Python 스크립트로 실행되는 경우
        return 'settings.json'

def get_room_settings_file_path():
    """실행 환경에 따라 적절한 room_settings.json 파일 경로 반환"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 빌드된 실행 파일인 경우
        base_dir = os.path.dirname(sys.executable)
        return os.path.join(base_dir, 'room_settings.json')
    else:
        # 일반 Python 스크립트로 실행되는 경우
        return 'room_settings.json'

class SettingsManager:
    def __init__(self):
        self.settings = self.load_settings()

    def load_settings(self):
        """JSON 파일에서 설정을 불러오기 (항상 디스크에서 새로 읽음)"""
        settings_file = get_settings_file_path()
        if not os.path.exists(settings_file):
            # 기본 설정
            return {
                "site1": "", 
                "site2": "", 
                "site3": "",
                "martin_count": 3,
                "martin_amounts": [1000, 2000, 4000]
            }
        
        # 파일 내용 읽기
        try:
            with open(settings_file, "r", encoding="utf-8") as file:
                settings = json.load(file)
                
                # 마틴 설정이 없을 경우 기본값 추가
                if "martin_count" not in settings:
                    settings["martin_count"] = 3
                if "martin_amounts" not in settings:
                    settings["martin_amounts"] = [1000, 2000, 4000]
                    
                print(f"[DEBUG] 설정 파일 '{settings_file}'에서 읽은 마틴 금액: {settings['martin_amounts']}")
                return settings
        except Exception as e:
            print(f"[ERROR] 설정 파일 '{settings_file}' 읽기 오류: {e}")
            # 오류 발생 시 기본 설정 반환
            return {
                "site1": "", 
                "site2": "", 
                "site3": "",
                "martin_count": 3,
                "martin_amounts": [1000, 2000, 4000]
            }
            
    # 기존 save_settings 메서드 수정
    def save_settings(self, site1, site2, site3, martin_count=3, martin_amounts=None, target_amount=0, 
                    double_half_start=20, double_half_stop=8):
        """입력된 사이트 정보와 마틴 설정, 목표 금액을 JSON 파일에 저장"""
        if martin_amounts is None:
            martin_amounts = [1000, 2000, 4000]
                
        self.settings = {
            "site1": site1, 
            "site2": site2, 
            "site3": site3,
            "martin_count": martin_count,
            "martin_amounts": martin_amounts,
            "target_amount": target_amount,
            "double_half_start": double_half_start,
            "double_half_stop": double_half_stop
        }
        
        settings_file = get_settings_file_path()
        with open(settings_file, "w", encoding="utf-8") as file:
            json.dump(self.settings, file, indent=4)
            print(f"[INFO] 설정이 '{settings_file}'에 저장되었습니다.")

    # 추가 메서드 - Double & Half 설정 가져오기
    def get_double_half_settings(self):
        """Double & Half 설정 반환 (시작값, 중지값)"""
        return (
            self.settings.get("double_half_start", 20),
            self.settings.get("double_half_stop", 8)
        )
            
    def get_sites(self):
        """저장된 사이트 목록 반환"""
        return (
            self.settings.get("site1", ""), 
            self.settings.get("site2", ""), 
            self.settings.get("site3", "")
        )
        
    def get_martin_settings(self):
        """마틴 설정 반환 (횟수, 금액 목록)"""
        return (
            self.settings.get("martin_count", 3),
            self.settings.get("martin_amounts", [1000, 2000, 4000])
        )
    
    def get_target_amount(self):
        """목표 금액 설정 반환 (항상 파일에서 새로 불러옴)"""
        # 설정 파일에서 다시 읽기
        fresh_settings = self.load_settings()
        target_amount = fresh_settings.get("target_amount", 0)
        
        # 디버깅용 로그
        print(f"[DEBUG] 최신 목표 금액 설정 로드: {target_amount:,}원")
        
        return target_amount
    
    # settings_manager.py에 추가할 메서드
    def get_double_half_settings(self):
        """Double & Half 설정 반환 (시작값, 중지값)"""
        return (
            self.settings.get("double_half_start", 20),
            self.settings.get("double_half_stop", 8)
        )