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
        
        # timeout 설정 (기본 10초)
        kwargs.setdefault('timeout', 10)
        
        self.logger.info(f"🌐 서버 요청: {method} {url}")
        if kwargs.get('json'):
            json_data = kwargs.get('json')
            if endpoint == "/api/rooms/get-prediction":
                # 예측값 요청의 경우 상세 로깅
                self.logger.info(f"📤 예측값 요청 데이터:")
                self.logger.info(f"  - room_id: {json_data.get('room_id')}")
                self.logger.info(f"  - 결과 개수: {len(json_data.get('current_results', []))}")
                self.logger.info(f"  - 전체 결과: {json_data.get('current_results', [])}")
            else:
                self.logger.debug(f"📤 요청 데이터: {json_data}")
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            if response.status_code == 200:
                result = response.json()
                if endpoint == "/api/rooms/get-prediction":
                    # 예측값 응답의 경우 상세 로깅
                    self.logger.info(f"✅ 예측값 서버 응답 성공:")
                    self.logger.info(f"  - status: {result.get('status')}")
                    self.logger.info(f"  - prediction: {result.get('next_prediction')}")
                    self.logger.info(f"  - message: {result.get('message', 'N/A')}")
                else:
                    self.logger.info(f"✅ 서버 응답 성공: {endpoint}")
                return result
            else:
                self.logger.error(f"❌ 서버 요청 실패: {response.status_code}")
                self.logger.error(f"❌ 응답 내용: {response.text}")
                return None
                
        except requests.exceptions.Timeout as e:
            self.logger.error(f"⏱️ 서버 요청 타임아웃: {endpoint} - {e}")
            return None
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"🔌 서버 연결 실패: {endpoint} - {e}")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ 서버 요청 오류: {endpoint} - {e}")
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
        """다음 예측값만 반환 - 상세 로그 추가"""
        # 🔥 로비 상태에서는 예측값 요청 안함
        if hasattr(self, '_cancel_current_requests') and self._cancel_current_requests:
            self.logger.debug("🚫 요청 중단 플래그 설정됨 - 예측값 요청 취소")
            return None
        
        # 🔍 요청 전 상세 정보 로깅
        self.logger.info(f"🎯 예측값 요청 준비:")
        self.logger.info(f"  - 방 ID: {room_id}")
        self.logger.info(f"  - 결과 데이터: {len(current_results)}개")
        self.logger.info(f"  - 최근 5개 결과: {current_results[-5:] if len(current_results) >= 5 else current_results}")
        
        # 🔍 결과 데이터 유효성 검사
        if not room_id:
            self.logger.error("❌ 예측값 요청 실패: room_id가 비어있음")
            return None
            
        if not current_results or len(current_results) < 5:
            self.logger.warning(f"⚠️ 결과 데이터 부족: {len(current_results)}개 (최소 5개 필요)")
            return None
        
        # P, B만 있는지 확인
        valid_results = [r for r in current_results if r in ['P', 'B']]
        if len(valid_results) != len(current_results):
            self.logger.warning(f"⚠️ 유효하지 않은 결과 포함: {current_results}")
        
        payload = {
            "room_id": room_id,
            "current_results": current_results
        }
        
        self.logger.info(f"🌐 서버 예측값 요청 전송...")
        response = self._make_request("POST", "/api/rooms/get-prediction", json=payload)
        
        # 🔍 응답 상세 분석
        if response:
            self.logger.info(f"📥 서버 응답 수신: {response}")
            
            status = response.get("status")
            if status == "success":
                prediction = response.get("next_prediction")
                self.logger.info(f"✅ 예측값 생성 성공: {prediction}")
                
                if prediction in ['P', 'B']:
                    return prediction
                else:
                    self.logger.error(f"❌ 유효하지 않은 예측값: {prediction}")
                    return None
            else:
                error_msg = response.get("message", "알 수 없는 오류")
                self.logger.error(f"❌ 서버 예측 실패: {status} - {error_msg}")
                return None
        else:
            self.logger.error("❌ 서버 응답 없음 또는 오류")
            return None

    def find_streak_rooms(self, user_id: str = "default", min_streak: int = 3) -> Optional[Dict]:
        """연패 방 검색"""
        self.logger.info(f"🔍 연패 방 검색 시작 (min_streak={min_streak})")
        
        response = self._make_request("POST", f"/api/rooms/find-streak?min_streak={min_streak}")
        
        if response:
            # 응답 구조 로깅
            self.logger.info(f"📥 find_streak_rooms 원본 응답: {response}")
            
            # 서버가 직접 방 목록을 반환하는 경우
            if isinstance(response, list):
                self.logger.info(f"🏠 연패 방 검색 완료: {len(response)}개 발견 (리스트 형태)")
                # 리스트를 표준 응답 형식으로 변환
                return {
                    "success": True,
                    "data": {
                        "rooms": response
                    }
                }
            
            # 표준 응답 형식인 경우
            rooms = response.get("data", {}).get("rooms", [])
            self.logger.info(f"🏠 연패 방 검색 완료: {len(rooms)}개 발견")
        else:
            self.logger.warning("❌ 연패 방 검색 응답 없음")
            
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