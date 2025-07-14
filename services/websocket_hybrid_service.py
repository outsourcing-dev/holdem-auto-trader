# services/websocket_hybrid_service.py - 서버 연동 버전
"""
JavaScript 하이브리드 웹소켓 서비스 - 필터링된 방 데이터 서버 전송
Evolution Gaming 웹소켓 메시지에서 filtered_room_mappings.json에 있는 방만 서버로 전송
"""

import json
import time
import logging
import os
import sys
from typing import Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from datetime import datetime


class WebSocketHybridService(QObject):
    """JavaScript 하이브리드 웹소켓 서비스 - 필터링된 방 데이터 서버 전송"""
    
    # Qt 시그널
    game_data_received = pyqtSignal(dict)
    connection_status_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    streak_room_found = pyqtSignal(dict)  # 연패 방 발견 시그널
    
    def __init__(self, devtools, server_client=None, logger=None):
        super().__init__()
        self.devtools = devtools
        self.server_client = server_client  # 서버 클라이언트 주입
        self.logger = logger or logging.getLogger(__name__)
        
        # 필터링된 방 ID 목록 로드
        self._load_filtered_room_mappings()
        
        # 상태 관리
        self.is_active = False
        self.is_connected = False
        self.websocket_url = ""
        
        # 메시지 분석용 카운터
        self.message_count = 0
        self.filtered_room_count = 0
        self.sent_to_server_count = 0
        
        # 연결 상태 체크 타이머
        self.status_check_timer = QTimer()
        self.status_check_timer.timeout.connect(self._check_connection_status)
        
        # 이미 처리한 방 결과 추적 (중복 방지)
        self.processed_room_results = set()
        
        self.logger.info("🔍 WebSocketHybridService 서버 연동 모드 초기화")
        
    def _load_filtered_room_mappings(self):
        """필터링된 방 매핑 로드"""
        try:
            # 필터링 JSON 파일 경로 찾기
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
                json_paths = [
                    os.path.join(base_dir, "filtered_room_mappings.json"),
                    os.path.join(base_dir, "_internal", "filtered_room_mappings.json")
                ]
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                json_paths = [
                    os.path.join(base_dir, "..", "filtered_room_mappings.json"),
                    os.path.join(os.path.dirname(base_dir), "filtered_room_mappings.json")
                ]
            
            self.filtered_room_ids = set()
            self.room_mappings = {}
            
            # 파일 찾기 및 로드
            for json_path in json_paths:
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        room_mappings = data.get('room_mappings', {})
                        
                        self.filtered_room_ids = set(room_mappings.keys())
                        self.room_mappings = room_mappings
                        
                    self.logger.info(f"📋 필터링 방 목록 로드 완료: {len(self.filtered_room_ids)}개")
                    
                    # 방 이름들 로그
                    for room_id, room_name in room_mappings.items():
                        self.logger.info(f"  {room_id} → {room_name}")
                    
                    return
            
            # 파일을 찾지 못한 경우
            self.logger.warning("❌ filtered_room_mappings.json 파일을 찾을 수 없습니다.")
            self.filtered_room_ids = set()
            self.room_mappings = {}
            
        except Exception as e:
            self.logger.error(f"필터링 방 목록 로드 실패: {e}")
            self.filtered_room_ids = set()
            self.room_mappings = {}

    def start_websocket_connection(self, websocket_url: str) -> bool:
        """JavaScript 웹소켓 연결 시작"""
        try:
            self.logger.info(f"🔌 필터링된 방 서버 전송용 웹소켓 연결 시작")
            self.logger.info(f"📍 URL: {websocket_url[:100]}...")
            
            if not self.devtools or not self.devtools.driver:
                self.logger.error("DevTools 연결이 없습니다")
                return False
            
            self.websocket_url = websocket_url
            
            # 서버 전송용 인터셉터 주입
            if not self._inject_server_interceptor():
                return False
            
            # 웹소켓 연결 시작
            if not self._start_javascript_websocket():
                return False
            
            # 연결 확인
            if not self._verify_connection():
                return False
            
            # 상태 체크 타이머 시작
            self.status_check_timer.start(5000)  # 5초마다 상태 체크
            
            self.is_active = True
            self.connection_status_changed.emit(True)
            
            self.logger.info("✅ 필터링된 방 서버 전송용 웹소켓 연결 성공")
            return True
            
        except Exception as e:
            self.logger.error(f"웹소켓 연결 실패: {e}")
            self.error_occurred.emit(f"연결 실패: {str(e)}")
            return False

    def _inject_server_interceptor(self) -> bool:
        """서버 전송용 인터셉터 주입"""
        try:
            # 서버 전송에 특화된 JavaScript 코드
            interceptor_script = """
            // 🎯 서버 전송용 필터링된 방 데이터 인터셉터
            (function() {
                console.log('🎯 서버 전송용 방 데이터 분석 모드 시작');
                
                // 분석용 저장소 초기화
                window.wsServerAnalysis = {
                    totalMessages: 0,
                    filteredMessages: 0,
                    sentToServer: 0,
                    roomData: new Map(),
                    lastProcessedRounds: new Map()  // 중복 방지용
                };
                
                // 원본 WebSocket 백업
                const OriginalWebSocket = window.WebSocket;
                
                // WebSocket 가로채기
                window.WebSocket = function(url, protocols) {
                    console.log('🔗 WebSocket 연결:', url);
                    
                    const ws = new OriginalWebSocket(url, protocols);
                    
                    if (url.includes('evo-games.com')) {
                        console.log('🎮 Evolution WebSocket 감지 - 서버 전송 모드 활성화');
                        window.gameWebSocket = ws;
                        
                        ws.addEventListener('message', function(event) {
                            const messageData = event.data;
                            window.wsServerAnalysis.totalMessages++;
                            
                            let analysisResult = {
                                id: window.wsServerAnalysis.totalMessages,
                                timestamp: new Date().toISOString(),
                                type: typeof messageData,
                                rawData: messageData,
                                isJSON: false,
                                parsedData: null,
                                hasRoomInfo: false,
                                roomId: null,
                                hasResults: false,
                                gameResults: null,
                                roundNumber: null
                            };
                            
                            // JSON 파싱 시도
                            if (typeof messageData === 'string') {
                                try {
                                    if (messageData.trim().startsWith('{') || messageData.trim().startsWith('[')) {
                                        const parsed = JSON.parse(messageData);
                                        analysisResult.isJSON = true;
                                        analysisResult.parsedData = parsed;
                                        
                                        // 방 데이터 추출
                                        const roomDataResult = extractRoomData(parsed);
                                        if (roomDataResult) {
                                            analysisResult.hasRoomInfo = true;
                                            analysisResult.roomId = roomDataResult.roomId;
                                            analysisResult.hasResults = roomDataResult.hasResults;
                                            
                                            if (roomDataResult.hasResults) {
                                                analysisResult.gameResults = roomDataResult.gameResults;
                                                analysisResult.roundNumber = roomDataResult.roundNumber;
                                                
                                                console.log(`🎯 게임 결과 감지: ${roomDataResult.roomId}, 결과: ${roomDataResult.gameResults}`);
                                            }
                                        }
                                    }
                                } catch (e) {
                                    // JSON 파싱 실패는 무시
                                }
                            }
                            
                            // Python으로 모든 분석 결과 전송
                            if (window.sendServerAnalysisResultToPython) {
                                try {
                                    window.sendServerAnalysisResultToPython(analysisResult);
                                } catch (error) {
                                    console.error('🚨 Python 전송 오류:', error);
                                }
                            }
                        });
                        
                        ws.addEventListener('open', function() {
                            console.log('✅ Evolution WebSocket 연결 성공');
                        });
                        
                        ws.addEventListener('close', function(event) {
                            console.log('❌ Evolution WebSocket 연결 종료');
                        });
                    }
                    
                    return ws;
                };
                
                // 방 ID 및 게임 결과 추출 함수
                function extractRoomData(data) {
                    if (!data || typeof data !== 'object') return null;
                    
                    // lobby.historyUpdated 메시지에서 게임 결과 추출
                    if (data.type === 'lobby.historyUpdated' && data.args) {
                        for (const roomId of Object.keys(data.args)) {
                            const roomData = data.args[roomId];
                            
                            if (roomData && roomData.results && Array.isArray(roomData.results)) {
                                const results = roomData.results;
                                
                                if (results.length > 0) {
                                    // 최근 10개 결과 추출
                                    const recentResults = [];
                                    for (let i = 0; i < results.length; i++) {
                                        const result = results[i];
                                        if (result && result.c) {
                                            recentResults.push(result.c);
                                        }
                                    }
                                    
                                    return {
                                        roomId: roomId,
                                        hasResults: true,
                                        gameResults: recentResults,
                                        roundNumber: results.length,
                                        latestResult: recentResults[recentResults.length - 1]
                                    };
                                }
                            }
                        }
                    }
                    
                    return null;
                }
                
                console.log('✅ 서버 전송용 인터셉터 설치 완료');
            })();
            """
            
            # JavaScript 코드 실행
            result = self.devtools.driver.execute_script(interceptor_script)
            
            self.logger.info("✅ 서버 전송용 인터셉터 주입 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"인터셉터 주입 실패: {e}")
            return False

    def _start_javascript_websocket(self) -> bool:
        """JavaScript 웹소켓 연결 시작"""
        try:
            callback_script = f"""
            // Python 분석 결과 콜백 함수 설정
            window.sendServerAnalysisResultToPython = function(analysisResult) {{
                const event = new CustomEvent('pythonServerAnalysisData', {{
                    detail: analysisResult
                }});
                document.dispatchEvent(event);
            }};
            
            document.addEventListener('pythonServerAnalysisData', function(event) {{
                window.lastServerAnalysisData = event.detail;
                window.lastServerAnalysisTimestamp = Date.now();
            }});
            
            // 실제 웹소켓 연결
            try {{
                console.log('🔌 Evolution 웹소켓 연결 시작');
                window.gameWebSocket = new WebSocket('{self.websocket_url}');
                console.log('✅ 웹소켓 연결 객체 생성 완료');
                return true;
            }} catch (wsError) {{
                console.error('🚨 웹소켓 연결 실패:', wsError);
                return false;
            }}
            """
            
            result = self.devtools.driver.execute_script(callback_script)
            
            if result:
                self.logger.info("✅ JavaScript 콜백 및 웹소켓 설정 성공")
                self._start_message_collection()
                return True
            else:
                self.logger.error("JavaScript 콜백 설정 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"JavaScript 웹소켓 시작 실패: {e}")
            return False

    def _start_message_collection(self):
        """메시지 수집 시작"""
        try:
            self.message_collection_timer = QTimer()
            self.message_collection_timer.timeout.connect(self._collect_and_process_messages)
            self.message_collection_timer.start(2000)  # 2초마다 수집
            
            self.logger.info("✅ 서버 전송용 메시지 수집 시작")
            
        except Exception as e:
            self.logger.error(f"메시지 수집 시작 오류: {e}")

    def _collect_and_process_messages(self):
        """메시지 수집 및 처리"""
        try:
            collection_script = """
            if (window.lastServerAnalysisData && window.lastServerAnalysisTimestamp) {
                const data = window.lastServerAnalysisData;
                const timestamp = window.lastServerAnalysisTimestamp;
                
                if (!window.processedServerAnalysisTimestamp || timestamp > window.processedServerAnalysisTimestamp) {
                    window.processedServerAnalysisTimestamp = timestamp;
                    return data;
                }
            }
            return null;
            """
            
            analysis_data = self.devtools.driver.execute_script(collection_script)
            
            if analysis_data:
                self._process_analysis_data(analysis_data)
                
        except Exception as e:
            self.logger.debug(f"메시지 수집 중 오류: {e}")

    def _process_analysis_data(self, analysis_data):
        """분석 데이터 처리 - 필터링된 방만 서버로 전송"""
        try:
            self.message_count += 1
            room_id = analysis_data.get('roomId')
            has_room_info = analysis_data.get('hasRoomInfo', False)
            has_results = analysis_data.get('hasResults', False)
            
            # 필터링된 방 ID인지 확인
            is_filtered_room = room_id and room_id in self.filtered_room_ids
            
            if is_filtered_room:
                self.filtered_room_count += 1
                mapped_room_name = self.room_mappings.get(room_id, room_id)
                
                self.logger.info(f"🎯 [필터링된 방 {self.filtered_room_count}] 방 ID: {room_id}")
                self.logger.info(f"📍 매핑된 방 이름: {mapped_room_name}")
                
                # 게임 결과가 있는 경우 서버로 전송
                if has_results:
                    game_results = analysis_data.get('gameResults', [])
                    round_number = analysis_data.get('roundNumber', 0)
                    
                    # 중복 방지 체크
                    result_key = f"{room_id}_{round_number}_{len(game_results)}"
                    if result_key not in self.processed_room_results:
                        self.processed_room_results.add(result_key)
                        
                        self.logger.info(f"🎮 게임 결과 발견! 방 ID: {room_id}")
                        self.logger.info(f"📊 최근 {len(game_results)}개 결과: {game_results}")
                        
                        # 서버로 전송
                        self._send_room_data_to_server(room_id, mapped_room_name, game_results, round_number)
                
                # Qt 시그널로 게임 데이터 전송
                game_data = {
                    'room_id': room_id,
                    'room_name': mapped_room_name,
                    'has_results': has_results,
                    'game_results': analysis_data.get('gameResults', []) if has_results else [],
                    'round_number': analysis_data.get('roundNumber', 0) if has_results else 0,
                    'latest_result': analysis_data.get('gameResults', [])[-1] if has_results and analysis_data.get('gameResults') else ''
                }
                
                self.game_data_received.emit(game_data)
            
            # 간단한 통계 출력
            if self.filtered_room_count > 0 and self.filtered_room_count % 5 == 0:
                self.logger.info(f"📊 통계: 총 {self.message_count}개 메시지, 필터링된 방 {self.filtered_room_count}개, 서버 전송 {self.sent_to_server_count}개")
                
        except Exception as e:
            self.logger.error(f"분석 데이터 처리 오류: {e}")

    def _send_room_data_to_server(self, room_id: str, room_name: str, game_results: list, round_number: int):
        """필터링된 방 데이터를 서버로 전송"""
        try:
            if not self.server_client:
                self.logger.warning("서버 클라이언트가 설정되지 않음")
                return
            
            self.logger.info(f"📡 서버로 데이터 전송: {room_name} ({room_id})")
            self.logger.info(f"📊 결과 데이터: {game_results}")
            
            # 서버가 기대하는 형식으로 데이터 구성
            payload = {
                "room_id": room_id,
                "mapped_room_name": room_name,  # room_name -> mapped_room_name
                "all_results": game_results,    # recent_results -> all_results  
                "total_results": len(game_results),  # round_number -> total_results
                "latest_result": game_results[-1] if game_results else ""
            }
            
            # 직접 requests로 전송 (server_client 사용하지 않고)
            import requests
            response = requests.post(
                f"{self.server_client.base_url}/api/rooms/results",
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    self.sent_to_server_count += 1
                    self.logger.info(f"✅ 서버 전송 성공: {room_name}")
                    
                    # 연패 정보 확인
                    current_streak = result.get("current_streak", 0)
                    if current_streak >= 3:
                        self.logger.info(f"🚨 연패 방 발견! {room_name} - {current_streak}연패")
                        
                        streak_data = {
                            'room_id': room_id,
                            'room_name': room_name,
                            'streak_count': current_streak,
                            'streak_type': 'Choice Pick Prediction',
                            'recent_results': game_results
                        }
                        
                        self.streak_room_found.emit(streak_data)
                    else:
                        self.logger.debug(f"연패 {current_streak}회: {room_name}")
                else:
                    self.logger.warning(f"❌ 서버 응답 실패: {result.get('message', 'Unknown error')}")
            else:
                self.logger.warning(f"❌ 서버 전송 HTTP 오류: {response.status_code} - {response.text}")
                    
        except Exception as e:
            self.logger.error(f"서버 데이터 전송 오류: {e}")
            
    def _verify_connection(self) -> bool:
        """연결 확인"""
        try:
            max_wait_time = 10
            check_interval = 0.5
            
            for attempt in range(int(max_wait_time / check_interval)):
                verification_script = """
                if (window.gameWebSocket) {
                    return {
                        connected: window.gameWebSocket.readyState === 1,
                        readyState: window.gameWebSocket.readyState,
                        url: window.gameWebSocket.url
                    };
                }
                return { connected: false, readyState: -1 };
                """
                
                result = self.devtools.driver.execute_script(verification_script)
                
                if result and result.get('connected'):
                    self.is_connected = True
                    self.logger.info(f"✅ 웹소켓 연결 확인됨")
                    return True
                
                time.sleep(check_interval)
            
            self.logger.warning("❌ 웹소켓 연결 확인 실패")
            return False
                
        except Exception as e:
            self.logger.error(f"연결 확인 오류: {e}")
            return False

    def _check_connection_status(self):
        """주기적 연결 상태 체크"""
        try:
            status_script = """
            const stats = window.wsServerAnalysis || {};
            return {
                connected: window.gameWebSocket ? window.gameWebSocket.readyState === 1 : false,
                totalMessages: stats.totalMessages || 0,
                filteredMessages: stats.filteredMessages || 0,
                sentToServer: stats.sentToServer || 0
            };
            """
            
            status = self.devtools.driver.execute_script(status_script)
            
            if status:
                was_connected = self.is_connected
                self.is_connected = status.get('connected', False)
                
                if was_connected != self.is_connected:
                    self.connection_status_changed.emit(self.is_connected)
                
        except Exception as e:
            self.logger.debug(f"연결 상태 체크 오류: {e}")

    def stop_websocket_connection(self):
        """웹소켓 연결 중지"""
        try:
            if not self.is_active:
                return
                
            self.logger.info("🛑 서버 전송용 웹소켓 연결 중지")
            
            # 타이머 중지
            if hasattr(self, 'status_check_timer'):
                self.status_check_timer.stop()
            
            if hasattr(self, 'message_collection_timer'):
                self.message_collection_timer.stop()
            
            # 최종 통계 출력
            self.logger.info(f"📊 최종 통계: 총 메시지 {self.message_count}개, 필터링된 방 {self.filtered_room_count}개, 서버 전송 {self.sent_to_server_count}개")
            
            # JavaScript 정리
            cleanup_script = """
            if (window.gameWebSocket) {
                try {
                    window.gameWebSocket.close();
                } catch(e) {
                    console.log('WebSocket 정리 중 오류:', e);
                }
            }
            console.log('🛑 서버 전송용 WebSocket 정리 완료');
            """
            
            self.devtools.driver.execute_script(cleanup_script)
            
            # 상태 초기화
            self.is_active = False
            self.is_connected = False
            
            self.connection_status_changed.emit(False)
            self.logger.info("✅ 서버 전송용 웹소켓 중지 완료")
            
        except Exception as e:
            self.logger.error(f"웹소켓 중지 중 오류: {e}")

    def get_connection_status(self) -> Dict[str, Any]:
        """연결 상태 정보 반환"""
        try:
            return {
                'active': self.is_active,
                'connected': self.is_connected,
                'websocket_url': self.websocket_url,
                'total_messages': self.message_count,
                'filtered_room_messages': self.filtered_room_count,
                'sent_to_server': self.sent_to_server_count,
                'filtering_ratio': (self.filtered_room_count/self.message_count*100) if self.message_count > 0 else 0,
                'total_filtered_rooms': len(self.filtered_room_ids)
            }
            
        except Exception as e:
            self.logger.error(f"연결 상태 확인 오류: {e}")
            return {'active': self.is_active, 'connected': False, 'error': str(e)}

    def force_reconnect(self) -> bool:
        """강제 재연결"""
        try:
            self.logger.info("🔄 서버 전송용 웹소켓 강제 재연결")
            self.stop_websocket_connection()
            time.sleep(2)
            
            if self.websocket_url:
                return self.start_websocket_connection(self.websocket_url)
            else:
                self.logger.error("재연결할 URL이 없습니다")
                return False
                
        except Exception as e:
            self.logger.error(f"강제 재연결 오류: {e}")
            return False

    def get_server_stats(self):
        """서버 전송 통계 반환"""
        return {
            'total_messages': self.message_count,
            'filtered_room_messages': self.filtered_room_count,
            'sent_to_server': self.sent_to_server_count,
            'total_filtered_rooms': len(self.filtered_room_ids),
            'room_mappings': self.room_mappings
        }

    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            self.stop_websocket_connection()
        except:
            pass