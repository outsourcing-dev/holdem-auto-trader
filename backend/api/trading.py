"""
트레이딩 제어 API
"""
import logging
import subprocess
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel

from api.auth import get_current_user, User
from core.trading_engine import TradingEngine
from core.trading_engine_v2 import TradingEngineV2
from api.websocket import websocket_manager

logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter()

# 전역 트레이딩 엔진 인스턴스 (V2 사용)
trading_engines: Dict[str, TradingEngineV2] = {}

# Pydantic 모델
class TradingStartRequest(BaseModel):
    site_key: str = "site1"  # site1, site2, site3 중 선택
    use_real_betting: bool = True  # 실제 베팅 사용 여부
    
class TradingStatusResponse(BaseModel):
    is_active: bool
    browser_launched: bool = False
    current_room: Optional[str] = None
    game_count: int = 0
    total_bet_amount: int = 0
    current_balance: Optional[int] = None
    martin_step: int = 0

class BettingRequest(BaseModel):
    room_name: str
    bet_type: str  # 'P' or 'B'
    amount: int

def get_trading_engine(username: str) -> TradingEngineV2:
    """사용자별 트레이딩 엔진 가져오기 (V2)"""
    if username not in trading_engines:
        trading_engines[username] = TradingEngineV2(username)
    return trading_engines[username]

@router.post("/start")
async def start_trading(
    request: TradingStartRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """브라우저 시작 (사이트 접속만, 베팅은 하지 않음)"""
    try:
        import json
        import os
        
        logger.info(f"브라우저 시작 요청: {current_user.username}, site_key: {request.site_key}")
        
        # settings.json 읽기
        settings_path = os.path.join(os.path.dirname(__file__), "..", "settings.json")
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        
        # 선택한 사이트 URL 가져오기
        site_url = settings.get(request.site_key, "")
        
        logger.info(f"선택된 사이트 URL: {site_url}")
        
        if not site_url:
            logger.error(f"{request.site_key}가 설정되지 않았습니다")
            raise HTTPException(
                status_code=400,
                detail=f"{request.site_key}가 설정되지 않았습니다"
            )
        
        engine = get_trading_engine(current_user.username)
        
        # 이미 실행 중인 엔진이 있으면 중지
        if engine.is_active or engine.browser_launched:
            await engine.stop_trading()
        
        # Martin 설정 저장
        engine.martin_strategy.martin_count = settings.get("martin_count", 3)
        engine.martin_strategy.martin_amounts = settings.get("martin_amounts", [10000, 20000, 30000])
        min_streak = settings.get("min_streak", 3)
        
        # 브라우저만 시작 (베팅은 안함)
        if request.use_real_betting:
            # V2 엔진 사용 - 브라우저만 실행
            background_tasks.add_task(
                engine.start_trading,
                site_url,
                min_streak,
                websocket_manager
            )
            logger.info(f"브라우저 시작: {current_user.username}, 사이트: {site_url}")
            
            return {
                "status": "browser_started",
                "message": f"브라우저를 시작합니다. 로그인 후 Evolution 게임에 접속해주세요.",
                "mode": "browser_only"
            }
        else:
            # 기존 시뮬레이션 모드 (향후 구현)
            return {
                "status": "simulation_mode",
                "message": "시뮬레이션 모드는 준비 중입니다."
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"브라우저 시작 오류: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"브라우저 시작 실패: {str(e)}"
        )

@router.post("/start-betting")
async def start_betting(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """베팅 시작 (사용자가 로그인 및 Evolution 게임 접속 후)"""
    try:
        engine = get_trading_engine(current_user.username)
        
        if not engine.browser_launched:
            logger.warning(f"브라우저가 실행되지 않음: {current_user.username}")
            raise HTTPException(
                status_code=400,
                detail="먼저 브라우저를 실행해주세요"
            )
        
        if engine.is_active:
            logger.warning(f"베팅이 이미 진행 중: {current_user.username}")
            raise HTTPException(
                status_code=400,
                detail="베팅이 이미 진행 중입니다"
            )
        
        # 백그라운드에서 베팅 시작 (Evolution 감지 후 자동 시작)
        background_tasks.add_task(
            engine.start_betting,
            websocket_manager
        )
        
        logger.info(f"베팅 시작 요청: {current_user.username} - Evolution 감지 대기")
        
        return {
            "status": "betting_started",
            "message": "베팅을 시작합니다. Evolution 게임을 감지하는 중..."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"트레이딩 시작 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"트레이딩 시작 실패: {str(e)}"
        )

@router.post("/stop")
async def stop_trading(current_user: User = Depends(get_current_user)):
    """트레이딩 중지"""
    try:
        engine = get_trading_engine(current_user.username)
        
        if not engine.is_active:
            logger.warning("실행 중인 트레이딩이 없습니다")
            return {
                "status": "not_running",
                "message": "실행 중인 트레이딩이 없습니다"
            }
        
        await engine.stop_trading()
        
        logger.info(f"트레이딩 중지: {current_user.username}")
        
        return {
            "status": "stopped",
            "message": "트레이딩을 중지했습니다"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"트레이딩 중지 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"트레이딩 중지 실패: {str(e)}"
        )

@router.get("/status", response_model=TradingStatusResponse)
async def get_trading_status(current_user: User = Depends(get_current_user)):
    """트레이딩 상태 조회"""
    try:
        engine = get_trading_engine(current_user.username)
        
        return TradingStatusResponse(
            is_active=engine.is_active,
            browser_launched=engine.is_active,  # V2에서는 is_active가 브라우저 상태를 나타냄
            current_room=engine.current_room,
            game_count=engine.game_count,
            total_bet_amount=engine.total_bet_amount,
            current_balance=engine.current_balance,
            martin_step=engine.martin_step
        )
        
    except Exception as e:
        logger.error(f"상태 조회 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"상태 조회 실패: {str(e)}"
        )

@router.post("/bet")
async def place_bet(
    request: BettingRequest,
    current_user: User = Depends(get_current_user)
):
    """수동 베팅 (선택적 기능)"""
    try:
        engine = get_trading_engine(current_user.username)
        
        if not engine.is_active:
            raise HTTPException(
                status_code=400,
                detail="트레이딩이 활성화되지 않았습니다"
            )
        
        result = await engine.place_bet(
            request.room_name,
            request.bet_type,
            request.amount
        )
        
        return {
            "status": "success",
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"베팅 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"베팅 실패: {str(e)}"
        )

@router.get("/statistics")
async def get_statistics(current_user: User = Depends(get_current_user)):
    """통계 정보 조회"""
    try:
        engine = get_trading_engine(current_user.username)
        
        stats = engine.get_statistics()
        
        return {
            "total_games": stats.get("total_games", 0),
            "wins": stats.get("wins", 0),
            "losses": stats.get("losses", 0),
            "ties": stats.get("ties", 0),
            "win_rate": stats.get("win_rate", 0),
            "total_profit": stats.get("total_profit", 0),
            "current_streak": stats.get("current_streak", 0)
        }
        
    except Exception as e:
        logger.error(f"통계 조회 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"통계 조회 실패: {str(e)}"
        )

@router.post("/emergency-stop")
async def emergency_stop(current_user: User = Depends(get_current_user)):
    """긴급 정지"""
    try:
        engine = get_trading_engine(current_user.username)
        
        # 강제 종료
        await engine.force_stop()
        
        # 다른 사용자들에게도 알림 (선택적)
        await websocket_manager.broadcast({
            "type": "emergency_stop",
            "user": current_user.username,
            "message": "긴급 정지가 실행되었습니다"
        })
        
        logger.warning(f"긴급 정지 실행: {current_user.username}")
        
        return {
            "status": "emergency_stopped",
            "message": "긴급 정지가 실행되었습니다"
        }
        
    except Exception as e:
        logger.error(f"긴급 정지 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"긴급 정지 실패: {str(e)}"
        )