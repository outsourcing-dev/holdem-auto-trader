"""
WebSocket 관리자 - 실시간 통신
"""
import logging
import json
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class WebSocketManager:
    """WebSocket 연결 관리"""
    
    def __init__(self):
        # 활성 연결 저장 (username -> WebSocket)
        self.active_connections: Dict[str, WebSocket] = {}
        # 연결된 WebSocket 집합
        self.connections: Set[WebSocket] = set()
    
    async def startup(self):
        """시작 시 초기화"""
        logger.info("WebSocket 매니저 초기화")
    
    async def shutdown(self):
        """종료 시 정리"""
        logger.info("WebSocket 연결 종료 중...")
        for websocket in list(self.connections):
            try:
                await websocket.close()
            except:
                pass
        self.connections.clear()
        self.active_connections.clear()
    
    async def connect(self, websocket: WebSocket):
        """새 WebSocket 연결"""
        await websocket.accept()
        self.connections.add(websocket)
        logger.info(f"WebSocket 연결 수락: {len(self.connections)}개 연결")
    
    def disconnect(self, websocket: WebSocket):
        """WebSocket 연결 해제"""
        self.connections.discard(websocket)
        
        # 사용자 연결 제거
        for username, ws in list(self.active_connections.items()):
            if ws == websocket:
                del self.active_connections[username]
                logger.info(f"사용자 연결 해제: {username}")
                break
        
        logger.info(f"WebSocket 연결 해제: {len(self.connections)}개 연결")
    
    async def authenticate(self, websocket: WebSocket, username: str):
        """WebSocket 인증"""
        self.active_connections[username] = websocket
        logger.info(f"WebSocket 인증: {username}")
        
        # 인증 성공 메시지
        await self.send_personal_message(
            {"type": "auth_success", "username": username},
            websocket
        )
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """특정 WebSocket에 메시지 전송"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"메시지 전송 실패: {e}")
            self.disconnect(websocket)
    
    async def send_to_user(self, username: str, message: dict):
        """특정 사용자에게 메시지 전송"""
        if username in self.active_connections:
            websocket = self.active_connections[username]
            await self.send_personal_message(message, websocket)
    
    async def broadcast(self, message: dict):
        """모든 연결에 메시지 브로드캐스트"""
        disconnected = []
        for websocket in self.connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"브로드캐스트 실패: {e}")
                disconnected.append(websocket)
        
        # 연결 해제된 WebSocket 제거
        for websocket in disconnected:
            self.disconnect(websocket)
    
    async def handle_message(self, websocket: WebSocket, data: dict):
        """수신 메시지 처리"""
        msg_type = data.get("type")
        
        if msg_type == "auth":
            # 인증 요청
            username = data.get("username")
            if username:
                await self.authenticate(websocket, username)
        
        elif msg_type == "ping":
            # 핑 응답
            await self.send_personal_message({"type": "pong"}, websocket)
        
        else:
            logger.warning(f"알 수 없는 메시지 타입: {msg_type}")
    
    async def send_game_update(self, username: str, game_data: dict):
        """게임 상태 업데이트 전송"""
        message = {
            "type": "game_update",
            "data": game_data
        }
        await self.send_to_user(username, message)
    
    async def send_betting_result(self, username: str, result: dict):
        """베팅 결과 전송"""
        message = {
            "type": "betting_result",
            "data": result
        }
        await self.send_to_user(username, message)
    
    async def send_room_change(self, username: str, room_info: dict):
        """방 변경 알림"""
        message = {
            "type": "room_change",
            "data": room_info
        }
        await self.send_to_user(username, message)
    
    async def send_balance_update(self, username: str, balance: int):
        """잔액 업데이트"""
        message = {
            "type": "balance_update",
            "data": {"balance": balance}
        }
        await self.send_to_user(username, message)
    
    async def send_error(self, username: str, error_msg: str):
        """에러 메시지 전송"""
        message = {
            "type": "error",
            "data": {"message": error_msg}
        }
        await self.send_to_user(username, message)
    
    async def send_status_update(self, username: str, status: dict):
        """상태 업데이트 전송"""
        message = {
            "type": "status_update",
            "data": status
        }
        await self.send_to_user(username, message)
    
    async def send_streak_rooms_update(self, username: str, rooms_data: dict):
        """연패방 정보 업데이트 전송"""
        message = {
            "type": "streak_rooms_update",
            "data": rooms_data
        }
        await self.send_to_user(username, message)
    
    async def send_betting_placed(self, username: str, betting_data: dict):
        """베팅 내역 전송"""
        message = {
            "type": "betting_placed",
            "data": betting_data
        }
        await self.send_to_user(username, message)

# 전역 WebSocket 매니저 인스턴스
websocket_manager = WebSocketManager()