# utils/unified_server_client.py
import requests
import logging
from typing import Dict, List, Optional, Any

class ServerClient:
    """통합 서버 클라이언트 - 싱글톤 패턴"""
    _instance = None
    _initialized = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, base_url: str = None, logger=None):
        # 이미 초기화된 경우 스킵
        if self._initialized:
            return
        
        # 서버 URL 설정 (하드코딩)
        if base_url:
            self.base_url = base_url.rstrip('/')
        else:
            self.base_url = "https://port-0-vacara-auto-trader1-m8s257i9c06c5ea2.sel4.cloudtype.app"
            
        self.logger = logger or logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.timeout = 15
        self._initialized = True
        
        self.logger.info(f"🔗 서버 클라이언트 초기화: {self.base_url}")
        
        # 서버 연결 테스트
        if not self._test_connection():
            self.logger.warning(f"⚠️ 서버 연결 테스트 실패: {self.base_url}")
    
    def _test_connection(self) -> bool:
        """서버 연결 테스트"""
        try:
            response = self.session.get(f"{self.base_url}/api/status", timeout=5)
            return response.status_code == 200
        except Exception as e:
            self.logger.debug(f"서버 연결 테스트 실패: {e}")
            return False

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """공통 요청 처리"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"서버 요청 실패: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"서버 연결 오류: {e}")
            return None

    # 기존 서버 API 메서드들 통합
    def get_server_status(self) -> bool:
        """서버 상태 확인"""
        result = self._make_request("GET", "/api/status")
        return bool(result and result.get("status") == "running")

    def calculate_streak(self, room_id: str, room_name: str, results: List[str]) -> Optional[Dict]:
        """연패 계산"""
        payload = {
            "room_id": room_id,
            "mapped_room_name": room_name,
            "all_results": results,
            "total_results": len(results),
            "latest_result": results[-1] if results else ""
        }
        
        response = self._make_request("POST", "/api/rooms/calculate-streak", json=payload)
        
        if response:
            self.logger.info(f"✅ 연패 계산 완료: {room_name} - {response.get('current_streak', 0)}연패")
            
        return response

    def verify_and_predict(self, room_id: str, current_results: List[str], expected_streak: int) -> Optional[Dict]:
        """연패 검증 + 예측값 반환 (핵심 API)"""
        payload = {
            "room_id": room_id,
            "current_results": current_results,
            "expected_streak": expected_streak
        }
        
        response = self._make_request("POST", "/api/rooms/verify-and-predict", json=payload)
        
        if response:
            status = response.get("status")
            self.logger.info(f"🔍 연패 검증 결과: {status}")
            
        return response

    def get_next_prediction(self, room_id: str, current_results: List[str]) -> Optional[str]:
        """다음 예측값만 반환"""
        payload = {
            "room_id": room_id,
            "current_results": current_results
        }
        
        response = self._make_request("POST", "/api/rooms/get-prediction", json=payload)
        
        if response and response.get("status") == "success":
            prediction = response.get("next_prediction")
            self.logger.info(f"🎯 예측값 생성: {prediction}")
            return prediction
            
        return None

    def find_streak_rooms(self, user_id: str = "default", min_streak: int = 3) -> Optional[Dict]:
        """연패 방 검색"""
        response = self._make_request("POST", f"/api/rooms/find-streak?min_streak={min_streak}")
        
        if response and response.get("status") == "success":
            rooms = response.get("streak_rooms", [])
            self.logger.info(f"🏠 연패 방 검색 완료: {len(rooms)}개 발견")
            
        return response

    def get_room_stats(self) -> Optional[Dict]:
        """방 통계 조회"""
        return self._make_request("GET", "/api/rooms/stats")

# 전역 인스턴스 생성 함수
def get_server_client(base_url: str = None, logger=None) -> ServerClient:
    """서버 클라이언트 인스턴스 반환
    
    Args:
        base_url: 서버 URL (None이면 기본 서버 주소 사용)
        logger: 로거 인스턴스
        
    Returns:
        ServerClient: 싱글톤 인스턴스
    """
    return ServerClient(base_url, logger)

def set_server_url(new_url: str) -> bool:
    """서버 URL 변경 (런타임에서)
    
    Args:
        new_url: 새로운 서버 URL
        
    Returns:
        bool: 변경 성공 여부
    """
    try:
        # 기존 인스턴스가 있으면 새로 초기화
        if ServerClient._instance:
            ServerClient._instance.base_url = new_url.rstrip('/')
            ServerClient._instance.logger.info(f"🔄 서버 URL 변경: {new_url}")
            return ServerClient._instance._test_connection()
        return False
    except Exception as e:
        logging.error(f"서버 URL 변경 실패: {e}")
        return False