import json
import os

SETTINGS_FILE = "settings.json"

class SettingsManager:
    def __init__(self):
        self.settings = self.load_settings()

    def load_settings(self):
        """JSON 파일에서 설정을 불러오기"""
        if not os.path.exists(SETTINGS_FILE):
            return {"site1": "", "site2": "", "site3": ""}
        
        with open(SETTINGS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    def save_settings(self, site1, site2, site3):
        """입력된 사이트 정보를 JSON 파일에 저장"""
        self.settings = {"site1": site1, "site2": site2, "site3": site3}
        with open(SETTINGS_FILE, "w", encoding="utf-8") as file:
            json.dump(self.settings, file, indent=4)

    def get_sites(self):
        """저장된 사이트 목록 반환"""
        return self.settings.get("site1", ""), self.settings.get("site2", ""), self.settings.get("site3", "")
