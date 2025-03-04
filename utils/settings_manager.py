import json
import os

SETTINGS_FILE = "settings.json"

class SettingsManager:
    def __init__(self):
        self.settings = self.load_settings()

    def load_settings(self):
        """JSON 파일에서 설정을 불러오기"""
        if not os.path.exists(SETTINGS_FILE):
            # 기본 설정
            return {
                "site1": "", 
                "site2": "", 
                "site3": "",
                "martin_count": 3,
                "martin_amounts": [1000, 2000, 4000]
            }
        
        with open(SETTINGS_FILE, "r", encoding="utf-8") as file:
            settings = json.load(file)
            
            # 마틴 설정이 없을 경우 기본값 추가
            if "martin_count" not in settings:
                settings["martin_count"] = 3
            if "martin_amounts" not in settings:
                settings["martin_amounts"] = [1000, 2000, 4000]
            
            return settings

    def save_settings(self, site1, site2, site3, martin_count=3, martin_amounts=None):
        """입력된 사이트 정보와 마틴 설정을 JSON 파일에 저장"""
        if martin_amounts is None:
            martin_amounts = [1000, 2000, 4000]
            
        self.settings = {
            "site1": site1, 
            "site2": site2, 
            "site3": site3,
            "martin_count": martin_count,
            "martin_amounts": martin_amounts
        }
        
        with open(SETTINGS_FILE, "w", encoding="utf-8") as file:
            json.dump(self.settings, file, indent=4)

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