# utils/server_client.py
import requests
import json
import logging
import websockets
import asyncio
from typing import Optional, Dict, List, Any
from urllib.parse import urlparse, parse_qs

class BaccaratServerClient:
    """바카라 서버와 통신하는 클라이언트 클래스"""
    
    def __init__(self, server_url="http://localhost:8080", logger=None):
        self.server_url = server_url
        self.logger = logger or logging.getLogger(__name__)
        self.ws_url = f"ws://{server_url.replace('http://', '').replace('https://', '')}"
        
        # 연결 상태 추적
        self.is_monitoring_active = False
        self.last_config_sent = None
        
    def extract_websocket_config(self, ws_url: str) -> Optional[Dict[str, str]]:
        """웹소켓 URL에서 설정 정보 추출"""
        try:
            parsed_url = urlparse(ws_url)
            query_params = parse_qs(parsed_url.query)
            
            # 경로에서 bare_session_id 추출
            path_parts = parsed_url.path.split('/')
            bare_session_id = path_parts[-1] if path_parts else ""
            
            # 쿼리 파라미터에서 값 추출
            session_id = query_params.get('EVOSESSIONID', [''])[0]
            instance_param = query_params.get('instance', [''])[0]
            instance = instance_param.split('-')[0] if instance_param else ''
            client_version = query_params.get('client_version', [''])[0]
            
            if not all([bare_session_id, session_id, instance, client_version]):
                self.logger.warning("URL에서 필수 설정값을 추출할 수 없습니다.")
                return None
            
            return {
                "session_id": session_id,
                "bare_session_id": bare_session_id,
                "instance": instance,
                "client_version": client_version
            }
        except Exception as e:
            self.logger.error(f"URL 파싱 오류: {e}")
            return None
    
    def send_websocket_config(self, ws_url: str, user_id: str) -> bool:
        """웹소켓 설정을 서버에 전송"""
        try:
            config = self.extract_websocket_config(ws_url)
            if not config:
                return False
            
            config["user_id"] = user_id
            self.last_config_sent = config.copy()  # 설정 저장
            
            response = requests.post(
                f"{self.server_url}/api/baccarat/config",
                json=config,
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info("웹소켓 설정 전송 성공")
                return True
            else:
                self.logger.error(f"웹소켓 설정 전송 실패: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"웹소켓 설정 전송 오류: {e}")
            return False
    
    def start_monitoring(self, user_id: str) -> bool:
        """서버에서 로비 모니터링 시작"""
        try:
            response = requests.post(
                f"{self.server_url}/api/baccarat/start/{user_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self.is_monitoring_active = True
                    self.logger.info("서버 모니터링 시작 성공")
                    return True
                else:
                    self.logger.error(f"서버 모니터링 시작 실패: {data.get('message')}")
                    return False
            else:
                self.logger.error(f"서버 모니터링 시작 실패: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"서버 모니터링 시작 오류: {e}")
            return False
    
    def stop_monitoring(self, user_id: str) -> bool:
        """서버에서 로비 모니터링 중지"""
        try:
            response = requests.post(
                f"{self.server_url}/api/baccarat/stop/{user_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self.is_monitoring_active = False
                    self.logger.info("서버 모니터링 중지 성공")
                    return True
                else:
                    self.logger.error(f"서버 모니터링 중지 실패: {data.get('message')}")
                    return False
            else:
                self.logger.error(f"서버 모니터링 중지 실패: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"서버 모니터링 중지 오류: {e}")
            return False
    
    def find_streak_rooms(self, user_id: str, streak_count: int = 3) -> Dict[str, Any]:
        """
        조건에 맞는 연패 방 검색
        
        Returns:
            Dict: 서버 응답 전체 (status, streak_rooms, analysis_statistics 등 포함)
        """
        try:
            response = requests.post(
                f"{self.server_url}/api/baccarat/find-streak-rooms",
                json={
                    "streak_count": streak_count,
                    "user_id": user_id
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    streak_rooms = data.get("streak_rooms", [])
                    self.logger.info(f"연패 방 검색 성공: {len(streak_rooms)}개 발견")
                    return data  # 전체 응답 반환
                else:
                    self.logger.error(f"연패 방 검색 실패: {data.get('message')}")
                    return {"status": "error", "message": data.get('message')}
            else:
                error_msg = f"HTTP {response.status_code}"
                self.logger.error(f"연패 방 검색 실패: {error_msg}")
                return {"status": "error", "message": error_msg}
                
        except Exception as e:
            self.logger.error(f"연패 방 검색 오류: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_monitoring_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """현재 모니터링 데이터 조회"""
        try:
            response = requests.get(
                f"{self.server_url}/api/baccarat/data/{user_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return data.get("monitor_data")
                else:
                    self.logger.error(f"모니터링 데이터 조회 실패: {data.get('message')}")
                    return None
            else:
                self.logger.error(f"모니터링 데이터 조회 실패: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"모니터링 데이터 조회 오류: {e}")
            return None
    
    def get_room_detailed_data(self, user_id: str, room_id: str) -> Optional[Dict[str, Any]]:
        """특정 방의 상세 데이터 조회"""
        try:
            response = requests.get(
                f"{self.server_url}/api/baccarat/room-data/{user_id}/{room_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return data
                else:
                    self.logger.error(f"방 데이터 조회 실패: {data.get('message')}")
                    return None
            else:
                self.logger.error(f"방 데이터 조회 실패: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"방 데이터 조회 오류: {e}")
            return None
    
    def get_server_status(self) -> bool:
        """서버 상태 확인"""
        try:
            response = requests.get(
                f"{self.server_url}/api/status",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "running":
                    self.logger.debug("서버 상태 정상")
                    return True
                    
            self.logger.warning("서버 상태 비정상")
            return False
            
        except Exception as e:
            self.logger.error(f"서버 상태 확인 오류: {e}")
            return False
    
    def test_room_prediction(self, user_id: str, room_id: str, streak_count: int = 3) -> Optional[Dict[str, Any]]:
        """특정 방의 연패 예측 테스트 (디버깅용)"""
        try:
            response = requests.get(
                f"{self.server_url}/api/baccarat/room-prediction-test/{user_id}/{room_id}",
                params={"streak_count": streak_count},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return data
                else:
                    self.logger.error(f"방 예측 테스트 실패: {data.get('message')}")
                    return None
            else:
                self.logger.error(f"방 예측 테스트 실패: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"방 예측 테스트 오류: {e}")
            return None
    
    async def connect_websocket(self, user_id: str, message_handler=None):
        """서버와 웹소켓 연결 (실시간 데이터 수신용)"""
        try:
            ws_url = f"{self.ws_url}/ws/baccarat/{user_id}"
            self.logger.info(f"웹소켓 연결 시도: {ws_url}")
            
            async with websockets.connect(ws_url) as websocket:
                self.logger.info("웹소켓 연결 성공")
                
                # 초기 데이터 수신 대기
                try:
                    init_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    init_data = json.loads(init_message)
                    if message_handler:
                        await message_handler(init_data)
                except asyncio.TimeoutError:
                    self.logger.warning("초기 데이터 수신 타임아웃")
                
                # 메시지 수신 루프
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        if message_handler:
                            await message_handler(data)
                            
                    except websockets.exceptions.ConnectionClosed:
                        self.logger.info("웹소켓 연결 종료")
                        break
                    except Exception as e:
                        self.logger.error(f"웹소켓 메시지 처리 오류: {e}")
                        continue
                        
        except Exception as e:
            self.logger.error(f"웹소켓 연결 오류: {e}")
            return False
    
    def setup_complete_monitoring(self, ws_url: str, user_id: str) -> bool:
        """
        완전한 모니터링 설정 (설정 전송 + 모니터링 시작)
        
        Args:
            ws_url: 웹소켓 URL
            user_id: 사용자 ID
            
        Returns:
            bool: 설정 완료 여부
        """
        try:
            # 1. 서버 상태 확인
            if not self.get_server_status():
                self.logger.error("서버가 실행되지 않거나 응답하지 않습니다.")
                return False
            
            # 2. 웹소켓 설정 전송
            if not self.send_websocket_config(ws_url, user_id):
                self.logger.error("웹소켓 설정 전송 실패")
                return False
            
            # 3. 모니터링 시작
            if not self.start_monitoring(user_id):
                self.logger.error("모니터링 시작 실패")
                return False
            
            self.logger.info("완전한 모니터링 설정 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"모니터링 설정 오류: {e}")
            return False
    
    def get_connection_status(self) -> Dict[str, Any]:
        """현재 연결 상태 정보 반환"""
        return {
            "server_url": self.server_url,
            "is_monitoring_active": self.is_monitoring_active,
            "last_config_sent": self.last_config_sent,
            "server_accessible": self.get_server_status()
        }

# 하위 호환성을 위한 별칭
ServerClient = BaccaratServerClient