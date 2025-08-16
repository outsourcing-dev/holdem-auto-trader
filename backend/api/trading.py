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
from api.websocket import websocket_manager

logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter()

# 전역 트레이딩 엔진 인스턴스 (사용자별 관리 필요시 dict로 변경)
trading_engines: Dict[str, TradingEngine] = {}

# Pydantic 모델
class TradingStartRequest(BaseModel):
    site_key: str = "site1"  # site1, site2, site3 중 선택
    
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

def get_trading_engine(username: str) -> TradingEngine:
    """사용자별 트레이딩 엔진 가져오기"""
    if username not in trading_engines:
        trading_engines[username] = TradingEngine(username)
    return trading_engines[username]

@router.post("/start")
async def start_trading(
    request: TradingStartRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """브라우저 시작 (사이트 접속만)"""
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
        
        # 이미 실행 중인 프로세스가 있으면 종료
        if engine.browser_process and engine.browser_process.poll() is None:
            logger.info(f"기존 브라우저 종료 (PID: {engine.browser_process.pid})")
            engine.browser_process.terminate()
            try:
                engine.browser_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                engine.browser_process.kill()
            engine.browser_process = None
        
        # 상태 초기화
        engine.browser_launched = False
        engine.is_active = False
        
        # Martin 설정 저장
        engine.martin_strategy.martin_count = settings.get("martin_count", 3)
        engine.martin_strategy.martin_amounts = settings.get("martin_amounts", [10000, 20000, 30000])
        engine.min_streak = settings.get("min_streak", 3)
        
        # 브라우저만 실행 (베팅은 시작하지 않음)
        background_tasks.add_task(
            engine.launch_browser_only,
            site_url,
            websocket_manager
        )
        
        logger.info(f"브라우저 시작: {current_user.username}, 사이트: {site_url}")
        
        return {
            "status": "browser_launched",
            "message": f"브라우저를 실행했습니다. 로그인 후 Evolution 게임에 접속해주세요."
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
    """베팅 시작 (사용자가 Evolution 게임 접속 후)"""
    try:
        engine = get_trading_engine(current_user.username)
        
        if not engine.browser_launched:
            raise HTTPException(
                status_code=400,
                detail="먼저 브라우저를 실행해주세요"
            )
        
        if engine.is_active:
            raise HTTPException(
                status_code=400,
                detail="베팅이 이미 진행 중입니다"
            )
        
        # 백그라운드에서 베팅 시작
        background_tasks.add_task(
            engine.start_betting,
            websocket_manager
        )
        
        logger.info(f"베팅 시작: {current_user.username}")
        
        return {
            "status": "betting_started",
            "message": f"베팅을 시작합니다"
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
            raise HTTPException(
                status_code=400,
                detail="실행 중인 트레이딩이 없습니다"
            )
        
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
            browser_launched=engine.browser_launched,
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