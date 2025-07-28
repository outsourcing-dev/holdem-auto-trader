# services/game_monitoring_service.py (웹소켓 하이브리드와 동일한 로거 출력 추가)
import logging
from selenium.webdriver.common.by import By
from modules.game_detector import GameDetector
import time
from utils.iframe_utils import switch_to_iframe_with_retry

class GameMonitoringService:
    """
    게임 모니터링 서비스 - 웹소켓 하이브리드와 동일한 로거 출력 포함
    """
    
    def __init__(self, devtools, main_window, logger=None):
        """게임 모니터링 서비스 초기화"""
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        self.devtools = devtools
        self.main_window = main_window
        self.game_detector = GameDetector()
        
        self.logger.info("GameMonitoringService 초기화 완료")

    def get_current_game_state_with_server_format(self, room_id=None, room_name=None, log_always=True, desired_pb_count=15):
        """
        현재 게임 상태 분석 후 웹소켓 하이브리드 서비스와 동일한 양식으로 로거 출력
        
        Args:
            room_id (str): 방 ID (웹소켓에서 받은 것과 매칭용)
            room_name (str): 방 이름
            log_always (bool): 항상 로그 출력 여부
            desired_pb_count (int): 원하는 P,B 결과 개수
            
        Returns:
            dict: 게임 상태 정보
        """
        try:
            if log_always:
                self.logger.info("📊 iframe에서 현재 게임 상태 분석 중...")
            
            # 기본 프레임으로 전환
            self.devtools.driver.switch_to.default_content()
            
            # iframe 전환 시도
            if not switch_to_iframe_with_retry(self.devtools.driver, max_retries=3, max_depth=2):
                self.logger.warning("iframe 전환 실패")
                return None
            
            # 직접 iframe에서 게임 결과 파싱
            game_state = self._parse_game_results_from_iframe(desired_pb_count)
            
            if game_state:
                # 웹소켓 하이브리드와 동일한 양식으로 로거 출력
                self._log_in_websocket_hybrid_format(game_state, room_id, room_name)
                
                if log_always:
                    round_num = game_state.get('round', 0)
                    result_count = len(game_state.get('filtered_results', []))
                    self.logger.info(f"✅ iframe 게임 상태 분석 완료: 라운드 {round_num}, P,B 결과 {result_count}개")
            else:
                self.logger.warning("❌ iframe에서 게임 상태를 감지할 수 없습니다")
            
            return game_state
            
        except Exception as e:
            self.logger.error(f"게임 상태 분석 중 오류: {e}")
            
            # 오류 발생 시 기본 프레임으로 복귀
            try:
                self.devtools.driver.switch_to.default_content()
            except:
                pass
            
            return None

    def _parse_game_results_from_iframe(self, desired_count=15):
        """
        iframe에서 직접 게임 결과 파싱 (P,B만 수집)
        
        Args:
            desired_count (int): 원하는 P,B 결과 개수
            
        Returns:
            dict: 게임 상태 정보
        """
        try:
            self.logger.info(f"🔍 iframe에서 P,B 게임 결과 직접 파싱 시작 (최대 {desired_count}개)")
            
            # 1. 라운드 번호 찾기
            round_number = self._find_round_number()
            
            # 2. 게임 결과 목록 찾기 (P,B만)
            game_results = self._find_game_results(desired_count)
            
            # 3. 최신 결과 찾기 (P,B만)
            latest_result = self._find_latest_result()
            
            # 결과 정리
            if game_results or latest_result or round_number:
                game_state = {
                    'round': round_number or 0,
                    'filtered_results': game_results or [],
                    'latest_result': latest_result or '',
                    'total_results': len(game_results) if game_results else 0
                }
                
                self.logger.info(f"📊 iframe 파싱 결과: 라운드={round_number}, P,B 결과={len(game_results or [])}개, 최신={latest_result}")
                return game_state
            else:
                self.logger.warning("❌ iframe에서 P,B 게임 데이터를 찾을 수 없습니다")
                return None
                
        except Exception as e:
            self.logger.error(f"iframe P,B 게임 결과 파싱 오류: {e}")
            return None

    def _find_round_number(self):
        """iframe에서 라운드 번호 찾기"""
        try:
            # 일반적인 라운드 표시 선택자들
            round_selectors = [
                "[class*='round']",
                "[class*='Round']",
                "[class*='game']",
                "[class*='Game']",
                "div[data-role*='round']",
                "span[data-role*='round']"
            ]
            
            for selector in round_selectors:
                try:
                    elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        # 숫자만 추출
                        import re
                        numbers = re.findall(r'\d+', text)
                        if numbers:
                            round_num = int(numbers[-1])  # 마지막 숫자 사용
                            if 1 <= round_num <= 100:  # 합리적인 범위
                                self.logger.debug(f"라운드 번호 발견: {round_num} (텍스트: {text})")
                                return round_num
                except:
                    continue
            
            self.logger.warning("라운드 번호를 찾을 수 없습니다")
            return 0
            
        except Exception as e:
            self.logger.error(f"라운드 번호 찾기 오류: {e}")
            return 0

    def _find_game_results(self, desired_count=None):
        """iframe에서 Bead Road의 SVG 좌표를 이용한 게임 결과 목록 찾기 (P,B만 수집)"""
        try:
            self.logger.info(f"🎯 Bead Road P,B 게임 결과 파싱 시작" + (f" (최대 {desired_count}개)" if desired_count else " (제한 없음)"))
            
            # Bead Road 컨테이너 안에서만 coordinates 요소들 찾기 (핵심 수정!)
            svg_elements = self.devtools.driver.find_elements(
                By.CSS_SELECTOR, 
                'svg[data-role="Bead-road"] svg[data-type="coordinates"]'
            )
            
            if not svg_elements:
                self.logger.warning("Bead Road coordinates 요소를 찾을 수 없습니다")
                return []
            
            self.logger.info(f"🔍 Bead Road에서 발견된 coordinates 요소: {len(svg_elements)}개")
            
            # 좌표별로 결과 정리
            coordinate_results = {}
            
            for svg in svg_elements:
                try:
                    # 직접 좌표 정보 가져오기
                    data_x = svg.get_attribute("data-x")  # X 좌표 읽기
                    data_y = svg.get_attribute("data-y")  # Y 좌표 읽기
                    
                    if data_x is None or data_y is None:
                        continue
                    
                    x = int(data_x)
                    y = int(data_y)
                    
                    # 결과 추출 방법 1: text 요소에서 직접 가져오기
                    result = None
                    try:
                        text_element = svg.find_element(By.CSS_SELECTOR, 'text')
                        text_content = text_element.text.strip()
                        if text_content in ['P', 'B', 'T']:
                            result = text_content
                            self.logger.debug(f"좌표 ({x}, {y}): {result} (text 요소)")
                    except:
                        pass
                    
                    # 결과 추출 방법 2: roadItem의 name 속성에서 가져오기
                    if not result:
                        try:
                            road_item = svg.find_element(By.CSS_SELECTOR, 'svg[data-type="roadItem"]')
                            name = road_item.get_attribute("name")
                            if name:
                                # "Player", "Player Player" → "Player", "Banker" → "Banker" 등 처리
                                if "Player" in name:
                                    result = "P"
                                elif "Banker" in name:
                                    result = "B"
                                elif "Tie" in name:
                                    result = "T"
                                
                                if result:
                                    self.logger.debug(f"좌표 ({x}, {y}): {result} (name: {name})")
                        except:
                            pass
                    
                    # 결과 추출 방법 3: fill 색상으로 판단
                    if not result:
                        try:
                            path_element = svg.find_element(By.CSS_SELECTOR, 'path[fill]')
                            fill_color = path_element.get_attribute("fill")
                            if fill_color:
                                if "#2E83FF" in fill_color or "blue" in fill_color.lower():
                                    result = "P"  # Player는 보통 파란색
                                elif "#EC2024" in fill_color or "red" in fill_color.lower():
                                    result = "B"  # Banker는 보통 빨간색
                                elif "#159252" in fill_color or "green" in fill_color.lower():
                                    result = "T"  # Tie는 보통 녹색
                                
                                if result:
                                    self.logger.debug(f"좌표 ({x}, {y}): {result} (색상: {fill_color})")
                        except:
                            pass
                    
                    if result:
                        # 좌표별로 저장 (x, y) -> result
                        coordinate_key = (x, y)
                        if coordinate_key in coordinate_results:
                            self.logger.warning(f"중복된 좌표 발견: {coordinate_key}, 기존: {coordinate_results[coordinate_key]}, 새로운: {result}")
                        else:
                            coordinate_results[coordinate_key] = result
                    else:
                        self.logger.debug(f"좌표 ({x}, {y}): 결과를 파싱할 수 없음")
                        
                except Exception as e:
                    self.logger.debug(f"SVG 요소 처리 중 오류: {e}")
                    continue
            
            if not coordinate_results:
                self.logger.warning("Bead Road에서 게임 결과를 찾을 수 없습니다")
                return []
            
            self.logger.info(f"🎯 Bead Road 유효한 좌표 결과: {len(coordinate_results)}개")
            
            # 좌표를 올바른 게임 순서대로 정렬
            sorted_results = self._sort_coordinates_to_game_sequence(coordinate_results)
            
            # P, B만 필터링 (T 제외) - 새로 추가된 부분
            filtered_pb_only = [result for result in sorted_results if result in ['P', 'B']]
            
            # 전체 데이터 로그 출력 (필터링 전후 모두 표시)
            self.logger.info(f"📊 Bead Road 전체 게임 결과: {len(sorted_results)}개 - {sorted_results}")
            self.logger.info(f"🎯 P,B만 필터링된 결과: {len(filtered_pb_only)}개 - {filtered_pb_only}")
            
            # desired_count가 지정된 경우에만 제한 적용
            if desired_count is not None and len(filtered_pb_only) > desired_count:
                filtered_pb_only = filtered_pb_only[-desired_count:]
                self.logger.info(f"🔍 최근 {desired_count}개 P,B 결과: {filtered_pb_only}")
            else:
                if desired_count is not None:
                    self.logger.info(f"🔍 P,B 결과 개수가 {desired_count}개 이하이므로 모든 결과 사용")
                else:
                    self.logger.info(f"🔍 제한 없이 모든 P,B 결과 사용: {len(filtered_pb_only)}개")
            
            return filtered_pb_only
                
        except Exception as e:
            self.logger.error(f"SVG P,B 게임 결과 찾기 오류: {e}")
            return []

    def _sort_coordinates_to_game_sequence(self, coordinate_results):
        """
        좌표를 게임 순서대로 정렬
        바카라 게임 순서: (0,0)→(0,1)→(0,2)→...→(0,5)→(1,0)→(1,1)→...
        즉, X축 우선, Y축 차순으로 정렬
        """
        try:
            if not coordinate_results:
                return []
            
            # 좌표별로 정렬 (X축 우선, Y축 차순) - 수정된 부분
            sorted_coordinates = sorted(coordinate_results.keys(), key=lambda coord: (coord[0], coord[1]))
            
            # 정렬된 순서대로 결과 배열 생성
            results = []
            for coord in sorted_coordinates:
                result = coordinate_results[coord]
                results.append(result)
                self.logger.debug(f"게임 순서: 좌표{coord} -> {result}")
            
            self.logger.info(f"🎯 좌표 정렬 완료: {len(results)}개 결과")
            return results
            
        except Exception as e:
            self.logger.error(f"좌표 정렬 오류: {e}")
            return list(coordinate_results.values())  # 실패 시 순서 무시하고 값만 반환
        
    def _find_latest_result(self):
        """iframe에서 최신 게임 결과 찾기 (P, B만)"""
        try:
            # 1. 최신 결과 표시 선택자들
            latest_selectors = [
                "[class*='latest']",
                "[class*='Last']", 
                "[class*='current']",
                "[class*='winner']",
                "[class*='outcome']"
            ]
            
            for selector in latest_selectors:
                try:
                    elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        result = self._extract_single_pb_from_element(element)
                        # P 또는 B만 허용 (T 제외)
                        if result and result in ['P', 'B']:
                            self.logger.debug(f"최신 P,B 결과 발견: {result}")
                            return result
                except:
                    continue
            
            # 2. 일반적인 결과에서 마지막 P 또는 B 사용
            results = self._find_game_results(10)  # 더 많이 가져와서 P,B 찾기
            if results:
                # P 또는 B인 마지막 결과 찾기
                for result in reversed(results):
                    if result in ['P', 'B']:
                        self.logger.debug(f"결과 목록에서 최신 P,B 결과: {result}")
                        return result
            
            self.logger.warning("최신 P,B 게임 결과를 찾을 수 없습니다")
            return ''
            
        except Exception as e:
            self.logger.error(f"최신 P,B 결과 찾기 오류: {e}")
            return ''

    def _extract_pb_from_element(self, element):
        """요소에서 P, B 패턴 추출 (T 제외)"""
        try:
            # 요소의 텍스트 내용
            text = element.text.strip()
            
            # 클래스명에서도 확인
            class_name = element.get_attribute('class') or ''
            
            # data 속성에서도 확인  
            data_attrs = []
            try:
                for attr in ['data-result', 'data-outcome', 'data-winner', 'data-value']:
                    value = element.get_attribute(attr)
                    if value:
                        data_attrs.append(value)
            except:
                pass
            
            # 모든 텍스트 합치기
            all_text = ' '.join([text, class_name] + data_attrs)
            
            return self._extract_pb_from_text(all_text, 20)
            
        except Exception as e:
            self.logger.debug(f"요소에서 P,B 추출 오류: {e}")
            return []

    def _extract_single_pb_from_element(self, element):
        """요소에서 단일 P, B 결과 추출 (T 제외)"""
        try:
            results = self._extract_pb_from_element(element)
            return results[-1] if results else None
        except:
            return None

    def _extract_pb_from_text(self, text, max_count=15):
        """텍스트에서 P, B 패턴만 추출 (T 제외)"""
        try:
            import re
            
            # P, B 패턴만 찾기 (T 제외)
            pattern = r'\b[PBpb]\b'
            matches = re.findall(pattern, text)
            
            # 대문자로 변환하고 P, B만 허용
            results = [match.upper() for match in matches if match.upper() in ['P', 'B']]
            
            # 최대 개수 제한
            if len(results) > max_count:
                results = results[-max_count:]
            
            return results
            
        except Exception as e:
            self.logger.debug(f"텍스트에서 P,B 추출 오류: {e}")
            return []

    def _log_in_websocket_hybrid_format(self, game_state, room_id=None, room_name=None):
        """
        웹소켓 하이브리드 서비스와 동일한 양식으로 로거 출력
        
        Args:
            game_state (dict): 게임 상태 정보
            room_id (str): 방 ID
            room_name (str): 방 이름
        """
        try:
            # 웹소켓 하이브리드에서 서버로 보내는 데이터와 동일한 양식 생성
            round_number = game_state.get('round', 0)
            filtered_results = game_state.get('filtered_results', [])
            latest_result = game_state.get('latest_result', '')
            
            # 서버 전송 양식과 동일하게 로거 출력
            self.logger.info(f"📡 iframe에서 데이터 추출: {room_name or 'Unknown'} ({room_id or 'Unknown'})")
            self.logger.info(f"📊 최근 {len(filtered_results)}개 P,B 결과: {filtered_results}")
            
            if latest_result:
                self.logger.info(f"🎮 최신 게임 결과: 라운드 {round_number}, 결과 {latest_result}")
            
            # 웹소켓 하이브리드의 서버 전송 payload와 동일한 형태로 로그
            payload_format = {
                "room_id": room_id or "iframe_detected",
                "mapped_room_name": room_name or "Unknown Room",
                "all_results": filtered_results,
                "total_results": len(filtered_results),
                "latest_result": latest_result,
                "round_number": round_number,
                "detection_method": "iframe_parsing"
            }
            
            self.logger.info(f"📋 서버 전송 형태 데이터:")
            self.logger.info(f"  - room_id: {payload_format['room_id']}")
            self.logger.info(f"  - mapped_room_name: {payload_format['mapped_room_name']}")
            self.logger.info(f"  - all_results: {payload_format['all_results']}")
            self.logger.info(f"  - total_results: {payload_format['total_results']}")
            self.logger.info(f"  - latest_result: {payload_format['latest_result']}")
            self.logger.info(f"  - round_number: {payload_format['round_number']}")
            self.logger.info(f"  - detection_method: {payload_format['detection_method']}")
            
            # 연패 계산 (웹소켓 하이브리드와 동일한 로직)
            if filtered_results:
                streak_info = self._calculate_streak_from_results(filtered_results)
                if streak_info['current_streak'] > 0:
                    self.logger.info(f"🔍 연패 분석 결과: {streak_info['streak_type']} {streak_info['current_streak']}연패")
                    
                    # 연패 기준 달성 여부 체크 (기본 3연패)
                    user_threshold = getattr(self, 'user_streak_threshold', 1)
                    if streak_info['current_streak'] >= user_threshold:
                        self.logger.info(f"🚨 연패 기준 달성! {room_name or 'Unknown'} - {streak_info['current_streak']}연패 (기준: {user_threshold})")
                else:
                    self.logger.info("📊 현재 연패 상태 없음")
            
        except Exception as e:
            self.logger.error(f"웹소켓 하이브리드 양식 로거 출력 오류: {e}")

    def _calculate_streak_from_results(self, results):
        """
        결과 리스트에서 연패 정보 계산 (P, B만 처리)
        
        Args:
            results (list): 게임 결과 리스트 ['P', 'B', 'P', ...]
            
        Returns:
            dict: 연패 정보 {'streak_type': str, 'current_streak': int}
        """
        try:
            if not results or len(results) == 0:
                return {'streak_type': 'None', 'current_streak': 0}
            
            # 최신 결과부터 역순으로 연패 체크
            latest_result = results[-1]
            current_streak = 0
            
            # P 또는 B만 유효한 결과로 처리
            if latest_result not in ['P', 'B']:
                return {'streak_type': 'None', 'current_streak': 0}
            
            # 최신 결과와 동일한 결과가 연속으로 나온 횟수 계산
            for result in reversed(results):
                if result == latest_result:
                    current_streak += 1
                else:
                    break
            
            # Choice Pick 방식의 연패 (P 또는 B 연속)
            if latest_result in ['P', 'B'] and current_streak >= 3:
                streak_type = f"Choice Pick ({latest_result})"
            else:
                streak_type = "None"
                current_streak = 0
            
            return {
                'streak_type': streak_type,
                'current_streak': current_streak
            }
            
        except Exception as e:
            self.logger.error(f"P,B 연패 계산 오류: {e}")
            return {'streak_type': 'Error', 'current_streak': 0}

    def verify_room_streak_status(self, expected_streak_count, room_id=None, room_name=None):
        """
        현재 방이 예상 연패 상태인지 확인하고 웹소켓 하이브리드 양식으로 로그 출력
        
        Args:
            expected_streak_count (int): 예상 연패 횟수
            room_id (str): 방 ID
            room_name (str): 방 이름
            
        Returns:
            bool: 연패 상태 일치 여부
        """
        try:
            self.logger.info(f"🔍 연패 상태 검증 시작: 예상 {expected_streak_count}연패")
            
            # 현재 게임 상태 분석 (웹소켓 하이브리드 양식으로 로그 출력)
            game_state = self.get_current_game_state_with_server_format(
                room_id=room_id, 
                room_name=room_name,
                log_always=True
            )
            
            if not game_state:
                self.logger.error("❌ 게임 상태 분석 실패 - 연패 검증 불가")
                return False
            
            # 연패 상태 계산
            filtered_results = game_state.get('filtered_results', [])
            streak_info = self._calculate_streak_from_results(filtered_results)
            
            actual_streak = streak_info['current_streak']
            streak_type = streak_info['streak_type']
            
            # 연패 일치 여부 확인
            is_match = actual_streak >= expected_streak_count
            
            if is_match:
                self.logger.info(f"✅ 연패 상태 일치: 실제 {actual_streak}연패 >= 예상 {expected_streak_count}연패")
                self.logger.info(f"🎯 연패 타입: {streak_type}")
            else:
                self.logger.warning(f"❌ 연패 상태 불일치: 실제 {actual_streak}연패 < 예상 {expected_streak_count}연패")
                self.logger.warning(f"⚠️ 이 방은 연패 조건에 맞지 않습니다")
            
            return is_match
            
        except Exception as e:
            self.logger.error(f"연패 상태 검증 오류: {e}")
            return False

    def send_room_data_to_server_format(self, room_id=None, room_name=None):
        """
        현재 방 데이터를 서버 전송 형태로 준비하고 로그 출력
        (실제 서버 전송은 하지 않고 로그만 출력)
        
        Args:
            room_id (str): 방 ID
            room_name (str): 방 이름
            
        Returns:
            dict: 서버 전송용 데이터 또는 None
        """
        try:
            self.logger.info(f"📡 서버 전송 형태 데이터 준비: {room_name} ({room_id})")
            
            # 현재 게임 상태 분석
            game_state = self.get_current_game_state_with_server_format(
                room_id=room_id,
                room_name=room_name,
                log_always=True
            )
            
            if not game_state:
                self.logger.error("❌ 게임 상태 분석 실패 - 서버 데이터 준비 불가")
                return None
            
            # 서버 전송용 payload 생성 (P, B만 필터링)
            filtered_results = game_state.get('filtered_results', [])
            
            # P, B만 필터링 (T 제거) - 이미 필터링되어 있지만 확실히 하기 위해
            filtered_results = [r for r in filtered_results if r in ['P', 'B']]
            latest_result = game_state.get('latest_result', '')
            round_number = game_state.get('round', 0)
            
            payload = {
                "room_id": room_id or "iframe_detected",
                "mapped_room_name": room_name or "Unknown Room",
                "all_results": filtered_results,
                "total_results": len(filtered_results),
                "latest_result": latest_result,
                "round_number": round_number,
                "timestamp": int(time.time() * 1000),  # 밀리초 단위
                "detection_method": "iframe_parsing"
            }
            
            self.logger.info(f"✅ 서버 전송용 데이터 준비 완료:")
            self.logger.info(f"📋 Payload: {payload}")
            
            # 연패 정보도 함께 출력
            if filtered_results:
                streak_info = self._calculate_streak_from_results(filtered_results)
                if streak_info['current_streak'] > 0:
                    self.logger.info(f"📊 연패 정보: {streak_info['streak_type']} {streak_info['current_streak']}연패")
            
            return payload
            
        except Exception as e:
            self.logger.error(f"서버 데이터 준비 오류: {e}")
            return None

    # 기존 메서드들은 그대로 유지
    def get_current_game_state(self, log_always=True, desired_pb_count=15):
        """기존 게임 상태 분석 메서드 (하위 호환성 유지)"""
        try:
            if log_always:
                self.logger.debug("현재 게임 상태 분석 중...")
            
            # 기본 프레임으로 전환
            self.devtools.driver.switch_to.default_content()
            
            # iframe 전환 시도
            if not switch_to_iframe_with_retry(self.devtools.driver, max_retries=3, max_depth=2):
                self.logger.warning("iframe 전환 실패")
                return None
            
            # 페이지 소스 가져오기
            try:
                html_content = self.devtools.driver.page_source
            except Exception as e:
                self.logger.error(f"페이지 소스 가져오기 실패: {e}")
                return None
            
            # 게임 상태 감지 (단순화된 버전)
            game_state = self.game_detector.detect_game_state(
                html_content, 
                desired_pb_count=min(desired_pb_count, 20)  # 최대 20개로 제한
            )
            
            if game_state and log_always:
                round_num = game_state.get('round', 0)
                result_count = len(game_state.get('filtered_results', []))
                self.logger.debug(f"게임 상태: 라운드 {round_num}, 결과 {result_count}개")
            
            return game_state
            
        except Exception as e:
            self.logger.error(f"게임 상태 분석 중 오류: {e}")
            
            # 오류 발생 시 기본 프레임으로 복귀
            try:
                self.devtools.driver.switch_to.default_content()
            except:
                pass
            
            return None

    def close_current_room(self):
        """현재 방 종료 - 단순화"""
        try:
            self.logger.info("현재 방 종료 시도")
            
            # 현재 창 개수 확인
            window_handles = self.devtools.driver.window_handles
            
            # 종료 버튼 찾기 시도
            if self._try_close_room():
                self.logger.info("방 종료 버튼 클릭 완료")
                time.sleep(2)  # 종료 대기
            else:
                self.logger.warning("방 종료 버튼을 찾을 수 없음")
            
            # 로비 창으로 전환
            return self._switch_to_lobby_window(window_handles)
            
        except Exception as e:
            self.logger.error(f"방 종료 중 오류: {e}")
            
            # 오류 발생 시에도 로비 창으로 복귀 시도
            try:
                window_handles = self.devtools.driver.window_handles
                return self._switch_to_lobby_window(window_handles)
            except:
                return False

    def _try_close_room(self):
        """방 종료 버튼 찾기 및 클릭 시도"""
        try:
            # 기본 프레임으로 전환
            self.devtools.driver.switch_to.default_content()
            
            # iframe으로 전환
            if not switch_to_iframe_with_retry(self.devtools.driver, max_retries=2):
                return False
            
            # 종료 버튼 선택자들 (단순화)
            close_selectors = [
                "button[data-role='close-button']",
                ".close-button",
                "[aria-label='Close']",
                "[title='Close']"
            ]
            
            # 종료 버튼 찾기
            for selector in close_selectors:
                try:
                    close_button = self.devtools.driver.find_element(By.CSS_SELECTOR, selector)
                    if close_button:
                        close_button.click()
                        return True
                except:
                    continue
            
            # JavaScript로 시도
            try:
                js_script = """
                var buttons = document.querySelectorAll('button, [role="button"]');
                for (var i = 0; i < buttons.length; i++) {
                    var btn = buttons[i];
                    if (btn.textContent.includes('Close') || 
                        btn.textContent.includes('Exit') ||
                        btn.getAttribute('aria-label') === 'Close') {
                        btn.click();
                        return true;
                    }
                }
                return false;
                """
                
                if self.devtools.driver.execute_script(js_script):
                    return True
                    
            except Exception as e:
                self.logger.warning(f"JavaScript 종료 시도 실패: {e}")
            
            return False
            
        except Exception as e:
            self.logger.warning(f"방 종료 시도 중 오류: {e}")
            return False

    def _switch_to_lobby_window(self, window_handles):
        """로비 창으로 전환 - 단순화"""
        try:
            # 창이 2개 이상 있으면 두 번째 창(로비)으로 전환
            if len(window_handles) >= 2:
                self.devtools.driver.switch_to.window(window_handles[1])
                self.logger.info("로비 창으로 전환 완료")
                
                # 로비 페이지인지 간단히 확인
                try:
                    current_url = self.devtools.driver.current_url
                    if "game" not in current_url.lower():
                        self.logger.debug("로비 페이지 확인됨")
                    else:
                        self.logger.warning("로비 페이지가 아닐 수 있음")
                except:
                    pass
                
                return True
                
            # 창이 하나만 있으면 그 창 사용
            elif len(window_handles) == 1:
                self.devtools.driver.switch_to.window(window_handles[0])
                self.logger.info("단일 창으로 전환")
                return True
                
            else:
                self.logger.warning("열린 창이 없습니다")
                return False
                
        except Exception as e:
            self.logger.error(f"창 전환 실패: {e}")
            return False

    def is_in_game_room(self):
        """현재 게임방에 있는지 확인 - 단순화"""
        try:
            current_url = self.devtools.driver.current_url
            
            # URL에 게임 관련 키워드가 있는지 확인
            game_keywords = ["game", "live", "table"]
            
            for keyword in game_keywords:
                if keyword in current_url.lower():
                    return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"게임방 확인 중 오류: {e}")
            return False

    def get_simple_game_info(self):
        """간단한 게임 정보만 반환"""
        try:
            game_state = self.get_current_game_state(log_always=False, desired_pb_count=5)
            
            if game_state:
                return {
                    'round': game_state.get('round', 0),
                    'latest_result': game_state.get('latest_result'),
                    'in_game': True
                }
            else:
                return {
                    'round': 0,
                    'latest_result': None,
                    'in_game': False
                }
                
        except Exception as e:
            self.logger.error(f"간단한 게임 정보 확인 중 오류: {e}")
            return {
                'round': 0,
                'latest_result': None,
                'in_game': False
            }