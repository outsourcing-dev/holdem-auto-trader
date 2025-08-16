"""
예측 서버 클라이언트 - 기존 unified_server_client.py 기반
"""
import logging
import aiohttp
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class PredictionClient:
    def __init__(self):
        # 기존 서버 URL 사용
        self.base_url = "https://port-0-vacara-auto-trader1-m8s257i9c06c5ea2.sel4.cloudtype.app"
        self.session = None
        
    async def _get_session(self):
        """aiohttp 세션 관리"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        return self.session
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """공통 요청 처리 (async 버전)"""
        url = f"{self.base_url}{endpoint}"
        
        logger.info(f"🌐 서버 요청: {method} {url}")
        
        try:
            session = await self._get_session()
            async with session.request(method, url, **kwargs) as response:
                if response.status == 200:
                    result = await response.json()
                    if endpoint == "/api/rooms/get-prediction":
                        logger.info(f"✅ 예측값 서버 응답 성공:")
                        logger.info(f"  - status: {result.get('status')}")
                        logger.info(f"  - prediction: {result.get('next_prediction')}")
                    else:
                        logger.info(f"✅ 서버 응답 성공: {endpoint}")
                    return result
                else:
                    logger.error(f"❌ 서버 요청 실패: {response.status}")
                    text = await response.text()
                    logger.error(f"❌ 응답 내용: {text}")
                    return None
                    
        except aiohttp.ClientTimeout:
            logger.error(f"⏱️ 서버 요청 타임아웃: {endpoint}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"🔌 서버 연결 실패: {endpoint} - {e}")
            return None
        except Exception as e:
            logger.error(f"❌ 서버 요청 오류: {endpoint} - {e}")
            return None
    
    async def test_connection(self) -> bool:
        """서버 연결 테스트"""
        try:
            result = await self._make_request("GET", "/api/status")
            return bool(result and result.get("status") == "running")
        except Exception as e:
            logger.debug(f"서버 연결 테스트 실패: {e}")
            return False
    
    async def get_prediction(self, room_id: str, results: List[str]) -> Optional[str]:
        """예측값 요청 - 기존 get_next_prediction 로직"""
        try:
            # 🔍 요청 전 상세 정보 로깅
            logger.info(f"🎯 예측값 요청 준비:")
            logger.info(f"  - 방 ID: {room_id}")
            logger.info(f"  - 결과 데이터: {len(results)}개")
            logger.info(f"  - 최근 5개 결과: {results[-5:] if len(results) >= 5 else results}")
            
            # 🔍 결과 데이터 유효성 검사
            if not room_id:
                logger.error("❌ 예측값 요청 실패: room_id가 비어있음")
                return None
                
            if not results or len(results) < 5:
                logger.warning(f"⚠️ 결과 데이터 부족: {len(results)}개 (최소 5개 필요)")
                return None
            
            # P, B만 있는지 확인
            valid_results = [r for r in results if r in ['P', 'B']]
            if len(valid_results) != len(results):
                logger.warning(f"⚠️ 유효하지 않은 결과 포함: {results}")
            
            payload = {
                "room_id": room_id,
                "current_results": results
            }
            
            logger.info(f"🌐 서버 예측값 요청 전송...")
            response = await self._make_request("POST", "/api/rooms/get-prediction", json=payload)
            
            # 🔍 응답 상세 분석
            if response:
                logger.info(f"📥 서버 응답 수신: {response}")
                
                status = response.get("status")
                if status == "success":
                    prediction = response.get("next_prediction")
                    logger.info(f"✅ 예측값 생성 성공: {prediction}")
                    
                    if prediction in ['P', 'B']:
                        return prediction
                    else:
                        logger.error(f"❌ 유효하지 않은 예측값: {prediction}")
                        return None
                else:
                    error_msg = response.get("message", "알 수 없는 오류")
                    logger.error(f"❌ 서버 예측 실패: {status} - {error_msg}")
                    return None
            else:
                logger.error("❌ 서버 응답 없음 또는 오류")
                return None
                
        except Exception as e:
            logger.error(f"예측값 요청 오류: {e}")
            return None
    
    async def find_streak_rooms(self, min_streak: int = 3) -> Optional[Dict]:
        """연패 방 검색"""
        logger.info(f"🔍 연패 방 검색 시작 (min_streak={min_streak})")
        
        response = await self._make_request("POST", f"/api/rooms/find-streak?min_streak={min_streak}")
        
        if response:
            # 응답 구조 로깅
            logger.info(f"📥 find_streak_rooms 원본 응답: {response}")
            
            # 서버가 직접 방 목록을 반환하는 경우
            if isinstance(response, list):
                logger.info(f"🏠 연패 방 검색 완료: {len(response)}개 발견 (리스트 형태)")
                return {
                    "success": True,
                    "data": {
                        "rooms": response
                    }
                }
            
            # 표준 응답 형식인 경우
            rooms = response.get("data", {}).get("rooms", [])
            logger.info(f"🏠 연패 방 검색 완료: {len(rooms)}개 발견")
        else:
            logger.warning("❌ 연패 방 검색 응답 없음")
            
        return response
    
    async def calculate_streak(self, room_id: str, room_name: str, results: List[str]) -> Optional[Dict]:
        """연패 계산"""
        payload = {
            "room_id": room_id,
            "mapped_room_name": room_name,
            "all_results": results,
            "total_results": len(results),
            "latest_result": results[-1] if results else ""
        }
        
        response = await self._make_request("POST", "/api/rooms/calculate-streak", json=payload)
        
        if response:
            logger.info(f"✅ 연패 계산 완료: {room_name} - {response.get('current_streak', 0)}연패")
            
        return response
    
    async def verify_and_predict(self, room_id: str, current_results: List[str], expected_streak: int) -> Optional[Dict]:
        """연패 검증 + 예측값 반환"""
        payload = {
            "room_id": room_id,
            "current_results": current_results,
            "expected_streak": expected_streak
        }
        
        response = await self._make_request("POST", "/api/rooms/verify-and-predict", json=payload)
        
        if response:
            status = response.get("status")
            logger.info(f"🔍 연패 검증 결과: {status}")
            
        return response
    
    async def close(self):
        """세션 정리"""
        if self.session and not self.session.closed:
            await self.session.close()