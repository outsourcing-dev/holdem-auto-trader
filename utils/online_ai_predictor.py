"""
온라인 학습 방식의 AI 예측기 모듈
- sklearn의 SGDClassifier를 사용한 온라인 학습
- 바카라 게임 결과 예측에 특화된 기능 제공
"""

from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import OneHotEncoder
import numpy as np
from typing import List, Optional, Dict, Tuple
import logging

class OnlineAIPredictor:
    """
    온라인 학습이 가능한 바카라 예측 AI
    - 최근 게임 결과를 기반으로 다음 게임 결과를 예측
    - 실제 결과가 나오면 온라인으로 모델 업데이트
    """
    
    def __init__(self, logger=None):
        """
        예측기 초기화
        
        Args:
            logger: 로깅을 위한 로거 객체
        """
        self.logger = logger
        self.model = None
        self.encoder = OneHotEncoder(sparse_output=False, categories=[['P', 'B']])
        self.history = []  # 학습에 사용된 최근 데이터 저장
        self.prediction_history = []  # 예측 결과 및 실제 결과 저장
        self.window_size = 10  # 예측에 사용할 이전 게임 수
        self.confidence_threshold = 0.51  # 예측 신뢰도 임계값
        self.min_training_samples = 10  # 초기 학습에 필요한 최소 샘플 수
        
        # 정확도 추적
        self.predictions_count = 0
        self.correct_predictions = 0
        
        # 초기 모델 생성
        self._create_new_model()
    
    def _create_new_model(self):
        """새로운 SGD 분류기 생성"""
        # 로깅
        if self.logger:
            self.logger.info("새로운 AI 예측 모델 생성")
            
        # SGD 분류기 생성 - 바이너리 분류 문제에 적합
        self.model = SGDClassifier(
            loss='log_loss',  # 로지스틱 회귀
            penalty='l2',     # L2 정규화
            alpha=0.0001,     # 정규화 강도
            max_iter=100,     # 최대 반복 횟수
            tol=1e-3,         # 수렴 허용 오차
            learning_rate='adaptive',  # 적응형 학습률
            eta0=0.01,        # 초기 학습률
            random_state=42   # 재현성을 위한 랜덤 시드
        )
        
        # 학습 데이터 초기화
        self.history = []
        self.prediction_history = []
        self.predictions_count = 0
        self.correct_predictions = 0
    
    def _prepare_features(self, results: List[str]) -> np.ndarray:
        """
        예측을 위한 특성 준비
        
        Args:
            results: 게임 결과 리스트 (최소 window_size 길이)
            
        Returns:
            특성 벡터
        """
        # 충분한 데이터가 있는지 확인
        if len(results) < self.window_size:
            # 데이터가 부족하면 패딩
            padded_results = ['P'] * (self.window_size - len(results)) + results
        else:
            # 최근 window_size 개의 결과만 사용
            padded_results = results[-self.window_size:]
        
        # 원-핫 인코딩
        encoded = self.encoder.fit_transform(np.array(padded_results).reshape(-1, 1))
        
        # 1차원 벡터로 변환
        return encoded.flatten().reshape(1, -1)
    
    def reset(self):
        """모델 및 관련 데이터 초기화"""
        self._create_new_model()
    
    def bulk_train(self, results: List[str]):
        """
        초기 데이터로 모델 학습
        
        Args:
            results: 전체 게임 결과 리스트
        """
        if len(results) < self.window_size + 1:
            if self.logger:
                self.logger.warning(f"초기 학습을 위한 데이터가 부족합니다: {len(results)} < {self.window_size + 1}")
            return False
            
        # 로깅
        if self.logger:
            self.logger.info(f"초기 데이터로 AI 모델 학습 시작: {len(results)}개 샘플")
        
        X = []  # 특성 배열
        y = []  # 레이블 배열
        
        # 학습 데이터 생성
        for i in range(len(results) - self.window_size):
            window = results[i:i+self.window_size]
            next_result = results[i+self.window_size]
            
            # 'T'는 학습에서 제외
            if next_result not in ['P', 'B']:
                continue
                
            features = self._prepare_features(window)
            X.append(features.flatten())
            y.append(next_result)
            
            # 학습 이력에 추가
            self.history.append((window.copy(), next_result))
        
        if not X or not y:
            if self.logger:
                self.logger.warning("유효한 학습 데이터가 없습니다.")
            return False
            
        # 모델 학습
        try:
            X_array = np.vstack(X)
            self.model.partial_fit(X_array, y, classes=['P', 'B'])
            
            # 로깅
            if self.logger:
                self.logger.info(f"AI 모델 초기 학습 완료: {len(X)}개 샘플")
                
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"모델 학습 중 오류 발생: {e}")
            return False
    
    def predict(self, results: List[str]) -> Tuple[str, float]:
        """
        다음 게임 결과 예측
        
        Args:
            results: 최근 게임 결과 리스트
            
        Returns:
            Tuple[str, float]: 예측 결과('P', 'B' 또는 'N')와 신뢰도
        """
        # 충분한 데이터가 있는지 확인
        if len(results) < self.window_size:
            if self.logger:
                self.logger.warning(f"예측을 위한 데이터가 부족합니다: {len(results)} < {self.window_size}")
            return 'N', 0.0
        
        # 모델이 충분히 학습되었는지 확인
        if len(self.history) < self.min_training_samples:
            if self.logger:
                self.logger.warning(f"모델이 충분히 학습되지 않았습니다: {len(self.history)} < {self.min_training_samples}")
            return 'N', 0.0
        
        try:
            features = self._prepare_features(results)
            proba = self.model.predict_proba(features)

            max_proba = np.max(proba[0])
            predicted_class_idx = np.argmax(proba[0])
            predicted_class = self.model.classes_[predicted_class_idx]

            # 예측 횟수가 8 이하면 confidence 기준만 적용
            if self.predictions_count <= 8:
                if max_proba >= self.confidence_threshold:
                    if self.logger:
                        self.logger.info(f"[초기 픽] confidence={max_proba:.4f} ≥ threshold={self.confidence_threshold:.4f}")
                    
                    # 예측 결과를 prediction_history에 저장 (추가된 부분)
                    prediction_entry = {
                        'prediction': predicted_class,
                        'confidence': max_proba,
                        'actual': None  # 실제 결과는 나중에 update에서 채워짐
                    }
                    self.prediction_history.append(prediction_entry)
                    
                    return predicted_class, max_proba
                else:
                    if self.logger:
                        self.logger.info(f"[초기 픽 차단] confidence={max_proba:.4f} < threshold={self.confidence_threshold:.4f}")
                    return 'N', max_proba

            # 예측 9회 이상이면 accuracy까지 같이 고려
            accuracy = self.get_accuracy()
            if max_proba >= self.confidence_threshold and accuracy >= 0.60:
                if self.logger:
                    self.logger.info(f"[정상 픽] confidence={max_proba:.4f}, accuracy={accuracy:.4f}")
                
                # 예측 결과를 prediction_history에 저장 (추가된 부분)
                prediction_entry = {
                    'prediction': predicted_class,
                    'confidence': max_proba,
                    'actual': None
                }
                self.prediction_history.append(prediction_entry)
                
                return predicted_class, max_proba
            else:
                if self.logger:
                    self.logger.info(f"[픽 거부] confidence={max_proba:.4f}, accuracy={accuracy:.4f} < 기준")
                return 'N', max_proba
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"예측 중 오류 발생: {e}")
            return 'N', 0.0
        
    def update(self, results: List[str], actual_result: str) -> bool:
        """
        실제 결과로 모델 업데이트
        
        Args:
            results: 이전 게임 결과 리스트
            actual_result: 실제 게임 결과
            
        Returns:
            bool: 업데이트 성공 여부
        """
        # 'T'는 학습에서 제외
        if actual_result not in ['P', 'B']:
            return False
            
        # 충분한 데이터가 있는지 확인
        if len(results) < self.window_size:
            return False
        
        # 최근 예측 결과 업데이트 (수정된 부분)
        if self.prediction_history and self.prediction_history[-1]['actual'] is None:
            self.prediction_history[-1]['actual'] = actual_result
            
            # 예측이 유효하고(N이 아님) 맞았는지 확인
            if self.prediction_history[-1]['prediction'] in ['P', 'B']:
                self.predictions_count += 1
                if self.prediction_history[-1]['prediction'] == actual_result:
                    self.correct_predictions += 1
        
        try:
            # 특성 준비
            features = self._prepare_features(results[:-1])  # 마지막 결과 제외
            
            # 모델 업데이트
            self.model.partial_fit(features, [actual_result], classes=['P', 'B'])
            
            # 학습 이력에 추가
            self.history.append((results[-self.window_size-1:-1].copy(), actual_result))
            
            # 이력 크기 제한
            if len(self.history) > 100:
                self.history = self.history[-100:]
                
            if len(self.prediction_history) > 50:
                self.prediction_history = self.prediction_history[-50:]
            
            # 로깅
            if self.logger:
                accuracy = self.get_accuracy()
                self.logger.info(f"AI 모델 업데이트 완료 (현재 정확도: {accuracy:.2f})")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"모델 업데이트 중 오류 발생: {e}")
            return False
        
    def get_accuracy(self) -> float:
        """
        현재 모델의 정확도 반환
        
        Returns:
            float: 정확도 (0.0~1.0)
        """
        if self.predictions_count == 0:
            return 0.0
        
        return self.correct_predictions / self.predictions_count

    def should_reset(self, game_count: int) -> bool:
        """
        모델 리셋이 필요한지 확인
        
        Args:
            game_count: 현재 게임 카운트
            
        Returns:
            bool: 리셋이 필요하면 True
        """
        # 60게임마다 리셋
        return game_count > 0 and game_count % 60 == 0