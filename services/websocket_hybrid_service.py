import json
import time
import logging
import os
import sys
from typing import Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from datetime import datetime
from utils.unified_server_client import get_server_client
from utils.common_iframe import IframeNavigator


class WebSocketHybridService(QObject):
    """JavaScript 하이브리드 웹소켓 서비스 - 연패 감지 및 자동 방 입장"""
    
    # Qt 시그널
    game_data_received = pyqtSignal(dict)
    connection_status_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    streak_room_found = pyqtSignal(dict)
    room_entry_requested = pyqtSignal(dict)  # 방 입장 요청 시그널
    
    def __init__(self, devtools, server_client=None, logger=None):
        super().__init__()
        self.devtools = devtools
        self.server_client = get_server_client()
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
        
        # 사용자 설정 연패 기준
        self.user_streak_threshold = 1  # 기본값
        self.auto_room_entry = True
        self._load_user_settings()
        
        # 방 입장 관리
        self.recent_room_entries = set()
        self.entry_cooldown_time = 300  # 5분 쿨다운
        self._last_entry_attempts = {}
        
        # 내부 연패 캐시
        self.internal_streak_cache = {}
        
        # 🔥 추가: 로비 모니터링 일시정지 플래그
        self._pause_lobby_monitoring = False
        self._in_game_room = False
    
        self.logger.info("🔍 WebSocketHybridService 연패 감지 및 자동 방 입장 모드 초기화")
        
    def _load_filtered_room_mappings(self):
        """필터링된 방 매핑 로드"""
        try:
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
            
            for json_path in json_paths:
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        room_mappings = data.get('room_mappings', {})
                        
                        self.filtered_room_ids = set(room_mappings.keys())
                        self.room_mappings = room_mappings
                        
                    self.logger.info(f"📋 필터링 방 목록 로드 완료: {len(self.filtered_room_ids)}개")
                    return
            
            self.logger.warning("❌ filtered_room_mappings.json 파일을 찾을 수 없습니다.")
            self.filtered_room_ids = set()
            self.room_mappings = {}
            
        except Exception as e:
            self.logger.error(f"필터링 방 목록 로드 실패: {e}")
            self.filtered_room_ids = set()
            self.room_mappings = {}

    def _load_user_settings(self):
        """사용자 설정 로드"""
        try:
            from utils.settings_manager import SettingsManager
            settings = SettingsManager()
            
            # 연패 기준 설정 로드 (기본값 3)
            self.user_streak_threshold = getattr(settings, 'streak_threshold', 1)
            self.auto_room_entry = getattr(settings, 'auto_room_entry', True)
            
            self.logger.info(f"📋 사용자 설정: 연패 기준 {self.user_streak_threshold}, 자동 입장 {self.auto_room_entry}")
            
        except Exception as e:
            self.logger.warning(f"사용자 설정 로드 실패: {e}, 기본값 사용")

    def update_streak_threshold(self, threshold: int):
        """연패 기준 업데이트"""
        self.user_streak_threshold = threshold
        self.logger.info(f"🎯 연패 기준 업데이트: {threshold}")

    def update_auto_room_entry(self, enabled: bool):
        """자동 방 입장 설정 업데이트"""
        self.auto_room_entry = enabled
        self.logger.info(f"🚪 자동 방 입장 설정: {enabled}")

    def start_websocket_connection(self, websocket_url: str) -> bool:
        """JavaScript 웹소켓 연결 시작"""
        try:
            self.logger.info(f"🔌 연패 감지 웹소켓 연결 시작")
            self.logger.info(f"📍 URL: {websocket_url[:100]}...")
            
            if not self.devtools or not self.devtools.driver:
                self.logger.error("DevTools 연결이 없습니다")
                return False
            
            self.websocket_url = websocket_url
            
            if not self._inject_server_interceptor():
                return False
            
            if not self._start_javascript_websocket():
                return False
            
            if not self._verify_connection():
                return False
            
            self.status_check_timer.start(5000)
            self.is_active = True
            self.connection_status_changed.emit(True)
            
            self.logger.info("✅ 연패 감지 웹소켓 연결 성공")
            return True
            
        except Exception as e:
            self.logger.error(f"웹소켓 연결 실패: {e}")
            self.error_occurred.emit(f"연결 실패: {str(e)}")
            return False

    def _inject_server_interceptor(self) -> bool:
        """서버 전송용 인터셉터 주입"""
        try:
            interceptor_script = """
            (function() {
                console.log('🎯 연패 감지용 방 데이터 분석 시작');
                
                window.wsServerAnalysis = {
                    totalMessages: 0,
                    filteredMessages: 0,
                    sentToServer: 0,
                    roomData: new Map(),
                    lastProcessedRounds: new Map()
                };
                
                const OriginalWebSocket = window.WebSocket;
                
                window.WebSocket = function(url, protocols) {
                    console.log('🔗 WebSocket 연결:', url);
                    
                    const ws = new OriginalWebSocket(url, protocols);
                    
                    if (url.includes('evo-games.com')) {
                        console.log('🎮 Evolution WebSocket 감지 - 연패 감지 모드 활성화');
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
                            
                            if (typeof messageData === 'string') {
                                try {
                                    if (messageData.trim().startsWith('{') || messageData.trim().startsWith('[')) {
                                        const parsed = JSON.parse(messageData);
                                        analysisResult.isJSON = true;
                                        analysisResult.parsedData = parsed;
                                        
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
                
                function extractRoomData(data) {
                    if (!data || typeof data !== 'object') return null;
                    
                    if (data.type === 'lobby.historyUpdated' && data.args) {
                        for (const roomId of Object.keys(data.args)) {
                            const roomData = data.args[roomId];
                            
                            if (roomData && roomData.results && Array.isArray(roomData.results)) {
                                const results = roomData.results;
                                
                                if (results.length > 0) {
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
                
                console.log('✅ 연패 감지용 인터셉터 설치 완료');
            })();
            """
            
            result = self.devtools.driver.execute_script(interceptor_script)
            self.logger.info("✅ 연패 감지용 인터셉터 주입 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"인터셉터 주입 실패: {e}")
            return False

    def _start_javascript_websocket(self) -> bool:
        """JavaScript 웹소켓 연결 시작"""
        try:
            callback_script = f"""
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
            
            self.logger.info("✅ 연패 감지용 메시지 수집 시작")
            
        except Exception as e:
            self.logger.error(f"메시지 수집 시작 오류: {e}")


    def _collect_and_process_messages(self):
        """메시지 수집 및 처리"""
        try:
            # 🔥 게임방에 있을 때는 로비 데이터 처리 중단
            if self._pause_lobby_monitoring:
                self.logger.debug("🚫 게임방 모드 - 로비 데이터 처리 중단")
                return
            
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

    def pause_lobby_monitoring(self):
        """로비 모니터링 일시정지"""
        self._pause_lobby_monitoring = True
        self._in_game_room = True
        self.logger.info("⏸️ 로비 모니터링 일시정지 - 게임방 모드")

    def resume_lobby_monitoring(self):
        """로비 모니터링 재개"""
        self._pause_lobby_monitoring = False
        self._in_game_room = False
        self.logger.info("▶️ 로비 모니터링 재개")
        
    def _process_analysis_data(self, analysis_data):
        """분석 데이터 처리 - 필터링된 방만 서버로 전송"""
        try:
            self.message_count += 1
            room_id = analysis_data.get('roomId')
            has_room_info = analysis_data.get('hasRoomInfo', False)
            has_results = analysis_data.get('hasResults', False)
            
            is_filtered_room = room_id and room_id in self.filtered_room_ids
            
            if is_filtered_room:
                self.filtered_room_count += 1
                mapped_room_name = self.room_mappings.get(room_id, room_id)
                
                self.logger.info(f"🎯 [필터링된 방 {self.filtered_room_count}] 방 ID: {room_id}")
                self.logger.info(f"📍 매핑된 방 이름: {mapped_room_name}")
                
                if has_results:
                    game_results = analysis_data.get('gameResults', [])
                    round_number = analysis_data.get('roundNumber', 0)
                    
                    result_key = f"{room_id}_{round_number}_{len(game_results)}"
                    if result_key not in self.processed_room_results:
                        self.processed_room_results.add(result_key)
                        
                        self.logger.info(f"🎮 게임 결과 발견! 방 ID: {room_id}")
                        self.logger.info(f"📊 최근 {len(game_results)}개 결과: {game_results}")
                        
                        # 서버로 전송 및 연패 체크
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
            
            if self.filtered_room_count > 0 and self.filtered_room_count % 5 == 0:
                self.logger.info(f"📊 통계: 총 {self.message_count}개 메시지, 필터링된 방 {self.filtered_room_count}개, 서버 전송 {self.sent_to_server_count}개")
                
        except Exception as e:
            self.logger.error(f"분석 데이터 처리 오류: {e}")

    # 🚫 기존 복잡한 코드를 다음으로 교체:
    def _send_room_data_to_server(self, room_id: str, room_name: str, game_results: list, round_number: int):
        """서버로 데이터 전송 및 연패 감지 - 통합 클라이언트 사용"""
        try:
            self.logger.info(f"📡 서버로 데이터 전송: {room_name} ({room_id})")
            
            # 🔥 통합 서버 클라이언트 사용
            result = self.server_client.calculate_streak(room_id, room_name, game_results)
            
            if result and result.get("status") == "success":
                current_streak = result.get("current_streak", 0)
                self.sent_to_server_count += 1
                
                self.logger.info(f"✅ 서버 전송 성공: {room_name} - {current_streak}연패")
                
                # 연패 정보 즉시 처리
                self._process_streak_response(room_id, room_name, current_streak, game_results)
                
            else:
                self.logger.warning(f"❌ 서버 전송 실패: {room_name}")
                        
        except Exception as e:
            self.logger.error(f"서버 데이터 전송 오류: {e}")
            
    def _process_streak_response(self, room_id: str, room_name: str, streak_count: int, recent_results: list):
        """서버 응답 연패 정보 처리 - 방 입장 로직"""
        try:
            self.logger.info(f"🔍 연패 응답 처리: {room_name} - {streak_count}연패 (기준: {self.user_streak_threshold})")
            
            # 🎯 사용자 설정 연패 기준과 비교
            if streak_count >= self.user_streak_threshold:
                self.logger.info(f"🚨 연패 기준 달성! {room_name} - {streak_count}연패 (기준: {self.user_streak_threshold})")
                
                streak_data = {
                    'room_id': room_id,
                    'room_name': room_name,
                    'streak_count': streak_count,
                    'streak_type': 'Choice Pick Prediction',
                    'recent_results': recent_results,
                    'detection_time': datetime.now().isoformat(),
                    'priority_score': self._calculate_priority_score(streak_count, recent_results),
                    'user_threshold': self.user_streak_threshold,
                    'meets_criteria': True
                }
                
                # 🔥 연패 방 발견 시그널
                self.streak_room_found.emit(streak_data)
                
                # 🚪 자동 방 입장 조건 체크
                if self.auto_room_entry and self._should_enter_room(room_id, streak_count):
                    self.logger.info(f"🎯 자동 방 입장 조건 만족: {room_name}")
                    self._request_room_entry(streak_data)
                
                # 📝 내부 캐시 업데이트
                self._update_internal_streak_cache(streak_data)
                
            else:
                self.logger.debug(f"연패 {streak_count}회: {room_name} (기준: {self.user_streak_threshold} 미만)")
                self._remove_from_streak_cache(room_id)
        
        except Exception as e:
            self.logger.error(f"연패 응답 처리 오류: {e}")

    def _should_enter_room(self, room_id: str, streak_count: int) -> bool:
        """방 입장 여부 판단"""
        try:
            current_time = time.time()
            
            # 쿨다운 체크
            last_attempt = self._last_entry_attempts.get(room_id, 0)
            if current_time - last_attempt < self.entry_cooldown_time:
                self.logger.debug(f"방 입장 쿨다운 중: {room_id}")
                return False
            
            # 중복 입장 방지
            entry_key = f"{room_id}_{streak_count}"
            if entry_key in self.recent_room_entries:
                self.logger.debug(f"이미 처리한 방 입장: {entry_key}")
                return False
            
            # 연패 수 상한선 체크 (너무 높으면 위험)
            if streak_count > 15:
                self.logger.warning(f"연패 수 너무 높음: {streak_count}, 입장 제외")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"방 입장 판단 오류: {e}")
            return False

    def _request_room_entry(self, streak_data: dict):
        """방 입장 요청"""
        try:
            room_id = streak_data['room_id']
            room_name = streak_data['room_name']
            streak_count = streak_data['streak_count']
            
            self.logger.info(f"🚪 방 입장 요청: {room_name} ({streak_count}연패)")
            
            # 입장 시도 기록
            current_time = time.time()
            self._last_entry_attempts[room_id] = current_time
            entry_key = f"{room_id}_{streak_count}"
            self.recent_room_entries.add(entry_key)
            
            # 방 입장 요청 시그널 발송
            self.room_entry_requested.emit(streak_data)
            
            # 쿨다운 타이머 설정 (5분 후 제거)
            QTimer.singleShot(self.entry_cooldown_time * 1000, 
                            lambda: self.recent_room_entries.discard(entry_key))
            
        except Exception as e:
            self.logger.error(f"방 입장 요청 오류: {e}")

    def _calculate_priority_score(self, streak_count: int, recent_results: list) -> float:
        """연패 방 우선순위 점수 계산"""
        try:
            base_score = streak_count
            bonus_score = 0
            
            if len(recent_results) >= 5:
                last_5 = recent_results[-5:]
                p_count = last_5.count('P')
                b_count = last_5.count('B')
                pattern_bonus = abs(p_count - b_count) * 0.2
                bonus_score += pattern_bonus
            
            data_bonus = min(len(recent_results) / 100, 1.0)
            bonus_score += data_bonus
            
            final_score = base_score + bonus_score
            
            self.logger.debug(f"우선순위 점수: {streak_count}연패 + {bonus_score:.2f}보너스 = {final_score:.2f}")
            
            return final_score
            
        except Exception as e:
            self.logger.error(f"우선순위 점수 계산 오류: {e}")
            return float(streak_count)

    def _update_internal_streak_cache(self, streak_data: dict):
        """내부 연패 캐시 업데이트"""
        try:
            room_id = streak_data['room_id']
            self.internal_streak_cache[room_id] = streak_data
            
            # 캐시 크기 제한 (최대 50개)
            if len(self.internal_streak_cache) > 50:
                sorted_items = sorted(
                    self.internal_streak_cache.items(),
                    key=lambda x: x[1].get('priority_score', 0),
                    reverse=True
                )
                self.internal_streak_cache = dict(sorted_items[:50])
            
            self.logger.debug(f"연패 캐시 업데이트: {room_id} (총 {len(self.internal_streak_cache)}개)")
            
        except Exception as e:
            self.logger.error(f"연패 캐시 업데이트 오류: {e}")

    def _remove_from_streak_cache(self, room_id: str):
        """연패 캐시에서 제거"""
        try:
            if room_id in self.internal_streak_cache:
                del self.internal_streak_cache[room_id]
                self.logger.debug(f"연패 캐시에서 제거: {room_id}")
        except Exception as e:
            self.logger.error(f"연패 캐시 제거 오류: {e}")

    def get_current_streak_rooms(self, min_streak: int = None) -> list:
        """현재 캐시된 연패 방 목록 반환"""
        try:
            if min_streak is None:
                min_streak = self.user_streak_threshold
            
            qualifying_rooms = []
            for room_data in self.internal_streak_cache.values():
                if room_data.get('streak_count', 0) >= min_streak:
                    qualifying_rooms.append(room_data)
            
            qualifying_rooms.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
            
            self.logger.info(f"현재 연패 방 목록: {len(qualifying_rooms)}개 (기준: {min_streak}연패 이상)")
            
            return qualifying_rooms
            
        except Exception as e:
            self.logger.error(f"연패 방 목록 조회 오류: {e}")
            return []

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
                
            self.logger.info("🛑 연패 감지 웹소켓 연결 중지")
            
            if hasattr(self, 'status_check_timer'):
                self.status_check_timer.stop()
            
            if hasattr(self, 'message_collection_timer'):
                self.message_collection_timer.stop()
            
            self.logger.info(f"📊 최종 통계: 총 메시지 {self.message_count}개, 필터링된 방 {self.filtered_room_count}개, 서버 전송 {self.sent_to_server_count}개")
            
            cleanup_script = """
            if (window.gameWebSocket) {
                try {
                    window.gameWebSocket.close();
                } catch(e) {
                    console.log('WebSocket 정리 중 오류:', e);
                }
            }
            console.log('🛑 연패 감지 WebSocket 정리 완료');
            """
            
            self.devtools.driver.execute_script(cleanup_script)
            
            self.is_active = False
            self.is_connected = False
            
            self.connection_status_changed.emit(False)
            self.logger.info("✅ 연패 감지 웹소켓 중지 완료")
            
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
                'total_filtered_rooms': len(self.filtered_room_ids),
                'streak_threshold': self.user_streak_threshold,
                'auto_room_entry': self.auto_room_entry,
                'cached_streak_rooms': len(self.internal_streak_cache),
                'paused': self._pause_lobby_monitoring,  # 🔥 추가
                'in_game_room': self._in_game_room  # 🔥 추가
            }
        except Exception as e:
            self.logger.error(f"연결 상태 확인 오류: {e}")
            return {'active': self.is_active, 'connected': False, 'error': str(e)}
        
    def force_reconnect(self) -> bool:
        """강제 재연결"""
        try:
            self.logger.info("🔄 연패 감지 웹소켓 강제 재연결")
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
            'room_mappings': self.room_mappings,
            'streak_threshold': self.user_streak_threshold,
            'auto_room_entry': self.auto_room_entry,
            'cached_streak_rooms': len(self.internal_streak_cache)
        }

    def debug_streak_cache(self):
        """연패 캐시 디버그 정보 출력"""
        try:
            cache_size = len(self.internal_streak_cache)
            self.logger.info(f"📊 연패 캐시 디버그 (총 {cache_size}개):")
            
            for room_id, room_data in self.internal_streak_cache.items():
                room_name = room_data.get('room_name', 'Unknown')
                streak_count = room_data.get('streak_count', 0)
                priority_score = room_data.get('priority_score', 0)
                
                self.logger.info(f"  {room_name}: {streak_count}연패 (점수: {priority_score:.2f})")
        
        except Exception as e:
            self.logger.error(f"연패 캐시 디버그 오류: {e}")

    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            self.stop_websocket_connection()
        except:
            pass