# utils/server_client.py - 방 데이터 및 연패 체크 API 추가
import requests
import json
import logging
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse, parse_qs

class BaccaratServerClient:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        # CloudType 배포된 서버 주소
        # self.base_url = "https://port-0-vacara-auto-trader1-m8s257i9c06c5ea2.sel4.cloudtype.app"
        self.base_url = "http://localhost:8080"

        self.timeout = 15
        self.session = requests.Session()
        
        # 연결 풀 설정
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=1,
            pool_maxsize=1,
            max_retries=3
        )
        self.session.mount('https://', adapter)

    def get_server_status(self) -> bool:
        """서버 상태 확인"""
        try:
            self.logger.info("🔍 서버 상태 확인 중...")
            response = self.session.get(
                f"{self.base_url}/api/status",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                status_data = response.json()
                self.logger.info(f"✅ 서버 상태: {status_data.get('status', 'unknown')}")
                return True
            else:
                self.logger.error(f"❌ 서버 상태 확인 실패: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            self.logger.error(f"❌ 서버 연결 타임아웃 ({self.timeout}초)")
            return False
        except Exception as e:
            self.logger.error(f"❌ 서버 상태 확인 오류: {e}")
            return False

    def send_room_results(self, room_id: str, room_name: str, recent_results: List[str], round_number: int) -> bool:
        """방 결과 데이터를 서버로 전송"""
        try:
            self.logger.info(f"📡 방 결과 데이터 전송: {room_name} ({room_id})")
            
            payload = {
                "room_id": room_id,
                "room_name": room_name,
                "recent_results": recent_results,
                "round_number": round_number,
                "timestamp": int(time.time() * 1000)  # 밀리초 단위 타임스탬프
            }
            
            response = self.session.post(
                f"{self.base_url}/api/rooms/results",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    self.logger.info(f"✅ 방 결과 전송 성공: {room_name}")
                    return True
                else:
                    self.logger.error(f"방 결과 전송 실패: {result.get('message', 'Unknown error')}")
                    return False
            else:
                self.logger.error(f"방 결과 전송 HTTP 오류: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"방 결과 전송 오류: {e}")
            return False

    def get_room_streak_info(self, room_id: str) -> Optional[Dict]:
        """서버에서 방의 연패 정보 조회"""
        try:
            self.logger.debug(f"🔍 연패 정보 조회: {room_id}")
            
            response = self.session.get(
                f"{self.base_url}/api/rooms/streak/{room_id}",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    streak_data = result.get("streak_data", {})
                    
                    streak_count = streak_data.get("streak_count", 0)
                    streak_type = streak_data.get("streak_type", "")
                    
                    if streak_count > 0:
                        self.logger.info(f"🔍 연패 정보: {room_id} - {streak_type} {streak_count}연패")
                    
                    return streak_data
                else:
                    self.logger.debug(f"연패 정보 없음: {room_id}")
                    return None
            else:
                self.logger.debug(f"연패 정보 조회 HTTP 오류: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.debug(f"연패 정보 조회 오류: {e}")
            return None

    def find_streak_rooms(self, min_streak: int = 3) -> Optional[List[Dict]]:
        """연패 방 목록 조회"""
        try:
            self.logger.info(f"🔍 {min_streak}연패 이상 방 검색 중...")
            
            payload = {
                "min_streak": min_streak
            }
            
            response = self.session.post(
                f"{self.base_url}/api/rooms/find-streak",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    streak_rooms = result.get("streak_rooms", [])
                    self.logger.info(f"✅ 연패 방 검색 완료: {len(streak_rooms)}개 발견")
                    
                    # 연패 방 정보 로그
                    for room in streak_rooms:
                        self.logger.info(f"  📍 {room.get('room_name', '')} - {room.get('streak_type', '')} {room.get('streak_count', 0)}연패")
                    
                    return streak_rooms
                else:
                    self.logger.info("연패 방을 찾지 못했습니다.")
                    return []
            else:
                self.logger.error(f"연패 방 검색 HTTP 오류: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"연패 방 검색 오류: {e}")
            return []

    def get_all_room_status(self) -> Optional[Dict]:
        """모든 방의 상태 정보 조회"""
        try:
            self.logger.info("📊 전체 방 상태 조회 중...")
            
            response = self.session.get(
                f"{self.base_url}/api/rooms/status",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    rooms_data = result.get("rooms_data", {})
                    self.logger.info(f"✅ 전체 방 상태 조회 완료: {len(rooms_data)}개 방")
                    return rooms_data
                else:
                    self.logger.warning(f"전체 방 상태 조회 실패: {result.get('message')}")
                    return None
            else:
                self.logger.warning(f"전체 방 상태 조회 HTTP 오류: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"전체 방 상태 조회 오류: {e}")
            return None

    def send_websocket_config(self, websocket_url: str, user_id: str) -> bool:
        """웹소켓 설정 전송 - 서버 API에 맞춤"""
        try:
            self.logger.info("📡 웹소켓 설정 추출 및 전송 중...")
            
            # 1단계: 웹소켓 URL에서 설정 추출
            config_data = self._extract_config_from_websocket_url(websocket_url)
            if not config_data:
                self.logger.error("웹소켓 URL에서 설정 추출 실패")
                return False
            
            # 2단계: 서버에 설정 전송
            config_payload = {
                "session_id": config_data["session_id"],
                "bare_session_id": config_data["bare_session_id"], 
                "instance": config_data["instance"],
                "client_version": config_data["client_version"],
                "user_id": user_id
            }
            
            response = self.session.post(
                f"{self.base_url}/api/baccarat/config",
                json=config_payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    self.logger.info("✅ 웹소켓 설정 전송 성공")
                    return True
                else:
                    self.logger.error(f"웹소켓 설정 전송 실패: {result.get('message', 'Unknown error')}")
                    return False
            else:
                self.logger.error(f"웹소켓 설정 전송 HTTP 오류: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"웹소켓 설정 전송 오류: {e}")
            return False

    def start_monitoring(self, user_id: str) -> bool:
        """모니터링 시작 - 타임아웃 증가"""
        try:
            self.logger.info(f"🎯 사용자 {user_id} 모니터링 시작 요청...")
            
            response = self.session.post(
                f"{self.base_url}/api/baccarat/start/{user_id}",
                timeout=30  # 30초로 증가
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    self.logger.info("✅ 모니터링 시작 성공")
                    return True
                else:
                    self.logger.error(f"모니터링 시작 실패: {result.get('message', 'Unknown error')}")
                    return False
            else:
                self.logger.error(f"모니터링 시작 HTTP 오류: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            self.logger.error(f"모니터링 시작 타임아웃 (30초)")
            return False
        except Exception as e:
            self.logger.error(f"모니터링 시작 오류: {e}")
            return False

    def stop_monitoring(self, user_id: str) -> bool:
        """모니터링 중지"""
        try:
            self.logger.info(f"🛑 사용자 {user_id} 모니터링 중지 요청...")
            
            response = self.session.post(
                f"{self.base_url}/api/baccarat/stop/{user_id}",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"모니터링 중지: {result.get('message', 'Success')}")
                return True
            else:
                self.logger.warning(f"모니터링 중지 HTTP 오류: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.warning(f"모니터링 중지 오류: {e}")
            return False

    def get_monitoring_data(self, user_id: str) -> Optional[Dict]:
        """모니터링 데이터 조회"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/baccarat/data/{user_id}",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    return result.get("monitor_data", {})
                else:
                    self.logger.warning(f"모니터링 데이터 조회 실패: {result.get('message')}")
                    return None
            else:
                self.logger.warning(f"모니터링 데이터 조회 HTTP 오류: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"모니터링 데이터 조회 오류: {e}")
            return None

    def _extract_config_from_websocket_url(self, websocket_url: str) -> Optional[Dict]:
        """웹소켓 URL에서 설정 정보 추출"""
        try:
            # URL 파싱
            parsed_url = urlparse(websocket_url)
            query_params = parse_qs(parsed_url.query)
            
            # 필요한 정보 추출
            bare_session_id = parsed_url.path.split('/')[-1]
            session_id = query_params.get('EVOSESSIONID', [''])[0]
            instance_param = query_params.get('instance', [''])[0]
            instance = instance_param.split('-')[0] if instance_param else ''
            client_version = query_params.get('client_version', [''])[0]
            
            # 값 검증
            if not all([bare_session_id, session_id, instance, client_version]):
                self.logger.error("웹소켓 URL에서 필수 정보를 추출할 수 없습니다.")
                self.logger.error(f"bare_session_id: {bare_session_id}")
                self.logger.error(f"session_id: {session_id}")
                self.logger.error(f"instance: {instance}")
                self.logger.error(f"client_version: {client_version}")
                return None
            
            config = {
                "session_id": session_id,
                "bare_session_id": bare_session_id,
                "instance": instance,
                "client_version": client_version
            }
            
            self.logger.info(f"설정 추출 성공: session_id={session_id[:20]}..., instance={instance}")
            return config
            
        except Exception as e:
            self.logger.error(f"웹소켓 URL 파싱 오류: {e}")
            return None

    def force_disconnect(self):
        """강제 연결 해제"""
        try:
            self.session.close()
            self.logger.info("서버 연결 강제 해제 완료")
        except:
            pass


# ✅ 기존 코드와의 호환성을 위한 별칭 클래스
class ServerClient(BaccaratServerClient):
    """기존 코드 호환성을 위한 별칭 클래스"""
    def __init__(self, logger=None):
        super().__init__(logger)
        self.logger.info("⚠️ ServerClient는 BaccaratServerClient의 별칭입니다. 새 코드에서는 BaccaratServerClient를 사용하세요.")


# ✅ 추가 호환성 함수들
def create_server_client(logger=None):
    """서버 클라이언트 생성 함수"""
    return BaccaratServerClient(logger)


# ✅ 모듈 레벨에서 import 가능하도록 export
__all__ = ['BaccaratServerClient', 'ServerClient', 'create_server_client']