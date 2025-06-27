import asyncio
import websockets

# 최신 URL로 테스트
websocket_url = "wss://tmgoodgame.evo-games.com/public/lobby/socket/v2/s6ndvz4e27uaykja?messageFormat=json&device=Desktop&features=opensAt%2CmultipleHero%2CshortThumbnails%2CskipInfosPublished%2Csmc%2CuniRouletteHistory%2CbacHistoryV2%2Cfilters%2CtableDecorations&instance=u8dc1q-s6ndvz4e27uaykja-&EVOSESSIONID=s6ndvz4e27uaykjas6ni34cajw7suif43c848a52b552b35d1e2e1db6cb3f934e4638d65a9a691c73&client_version=6.20250622.233648.52711-05f17fa7ac"

async def quick_test():
    try:
        async with websockets.connect(websocket_url, timeout=5) as ws:
            print("✅ 연결 성공!")
            return True
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        return False

# 실행
asyncio.run(quick_test())