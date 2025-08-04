# utils/server_test.py
"""
서버 예측값 요청 테스트 스크립트
베팅이 안되는 원인이 서버 문제인지 확인
"""

import logging
import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.unified_server_client import get_server_client

def test_server_prediction():
    """서버 예측값 요청 테스트"""
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    print("=" * 60)
    print("🧪 서버 예측값 요청 테스트 시작")
    print("=" * 60)
    
    # 서버 클라이언트 초기화
    server_client = get_server_client(logger=logger)
    
    # 테스트 데이터
    test_cases = [
        {
            "name": "기본 테스트",
            "room_id": "test_room_001",
            "results": ["P", "B", "P", "P", "B", "P", "B", "B", "P", "B"]
        },
        {
            "name": "긴 결과 테스트",
            "room_id": "test_room_002", 
            "results": ["P", "B", "P", "P", "B", "P", "B", "B", "P", "B", "P", "B", "P", "B", "P"]
        },
        {
            "name": "최소 데이터 테스트",
            "room_id": "test_room_003",
            "results": ["P", "B", "P", "B", "P"]
        },
        {
            "name": "부족한 데이터 테스트",
            "room_id": "test_room_004",
            "results": ["P", "B", "P"]
        },
        {
            "name": "빈 room_id 테스트",
            "room_id": "",
            "results": ["P", "B", "P", "B", "P"]
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 테스트 {i}: {test_case['name']}")
        print(f"  - 방 ID: '{test_case['room_id']}'")
        print(f"  - 결과 데이터: {test_case['results']}")
        
        try:
            prediction = server_client.get_next_prediction(
                room_id=test_case['room_id'],
                current_results=test_case['results']
            )
            
            if prediction:
                print(f"  ✅ 성공: 예측값 = {prediction}")
                results.append({
                    "test": test_case['name'],
                    "success": True,
                    "prediction": prediction
                })
            else:
                print(f"  ❌ 실패: 예측값 없음")
                results.append({
                    "test": test_case['name'], 
                    "success": False,
                    "prediction": None
                })
                
        except Exception as e:
            print(f"  💥 오류: {e}")
            results.append({
                "test": test_case['name'],
                "success": False,
                "error": str(e)
            })
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r.get('success', False))
    total_count = len(results)
    
    print(f"성공: {success_count}/{total_count}")
    print(f"실패: {total_count - success_count}/{total_count}")
    
    for result in results:
        status = "✅" if result.get('success', False) else "❌"
        test_name = result['test']
        
        if result.get('success', False):
            prediction = result.get('prediction', 'N/A')
            print(f"{status} {test_name}: {prediction}")
        else:
            error = result.get('error', '예측값 없음')
            print(f"{status} {test_name}: {error}")
    
    print("\n" + "=" * 60)
    
    # 서버 연결 상태 최종 확인
    print("🔗 서버 연결 상태 최종 확인...")
    status = server_client.get_server_status()
    print(f"서버 상태: {'🟢 정상' if status else '🔴 비정상'}")
    
    return success_count > 0

if __name__ == "__main__":
    try:
        success = test_server_prediction()
        if success:
            print("\n🎉 테스트 완료: 서버 예측값 요청이 정상 작동합니다.")
            sys.exit(0)
        else:
            print("\n❌ 테스트 실패: 서버 예측값 요청에 문제가 있습니다.")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 테스트 중 치명적 오류: {e}")
        sys.exit(1)