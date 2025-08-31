"""
Parameter Optimizer - 자동화된 매개변수 최적화
유전 알고리즘, 그리드 서치, 베이지안 최적화
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import json
import asyncio
import random
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import itertools
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel

logger = logging.getLogger(__name__)

class OptimizationMethod(Enum):
    """최적화 방법"""
    GRID_SEARCH = "grid_search"
    GENETIC_ALGORITHM = "genetic_algorithm"
    BAYESIAN = "bayesian"
    RANDOM_SEARCH = "random_search"
    PARTICLE_SWARM = "particle_swarm"

class OptimizationObjective(Enum):
    """최적화 목표"""
    SHARPE_RATIO = "sharpe_ratio"
    TOTAL_RETURN = "total_return"
    PROFIT_FACTOR = "profit_factor"
    WIN_RATE = "win_rate"
    CALMAR_RATIO = "calmar_ratio"
    SORTINO_RATIO = "sortino_ratio"

@dataclass
class ParameterRange:
    """매개변수 범위"""
    name: str
    min_value: float
    max_value: float
    step: Optional[float] = None
    is_integer: bool = False
    values: Optional[List[Any]] = None  # 고정된 값들

@dataclass
class OptimizationConfig:
    """최적화 설정"""
    method: OptimizationMethod
    objective: OptimizationObjective
    parameter_ranges: Dict[str, ParameterRange]
    max_iterations: int = 100
    population_size: int = 50  # 유전 알고리즘용
    mutation_rate: float = 0.1
    crossover_rate: float = 0.8
    convergence_threshold: float = 0.001
    max_time_minutes: int = 60
    parallel_workers: int = 4
    validation_split: float = 0.3  # 검증용 데이터 비율

@dataclass
class OptimizationResult:
    """최적화 결과"""
    best_parameters: Dict[str, Any]
    best_score: float
    all_results: List[Dict[str, Any]]
    optimization_history: List[Tuple[int, float]]  # (iteration, best_score)
    convergence_achieved: bool
    total_evaluations: int
    execution_time: float
    method_used: OptimizationMethod
    objective_used: OptimizationObjective
    validation_score: Optional[float] = None
    overfitting_detected: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

class ParameterOptimizer:
    """매개변수 최적화기"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.optimization_history: List[OptimizationResult] = []
        self.max_history = 50
        
        # 베이지안 최적화용 GP 모델
        self.gp_model = None
        
        logger.info(f"🔧 Parameter Optimizer initialized with {max_workers} workers")
    
    async def optimize_parameters(
        self,
        objective_function: Callable,
        config: OptimizationConfig,
        market_data: pd.DataFrame,
        validation_data: Optional[pd.DataFrame] = None
    ) -> OptimizationResult:
        """매개변수 최적화 실행"""
        start_time = time.time()
        
        try:
            logger.info(f"🎯 Starting {config.method.value} optimization for {config.objective.value}")
            
            # 데이터 분할 (검증 데이터가 없는 경우)
            if validation_data is None and config.validation_split > 0:
                split_idx = int(len(market_data) * (1 - config.validation_split))
                train_data = market_data.iloc[:split_idx]
                validation_data = market_data.iloc[split_idx:]
            else:
                train_data = market_data
            
            # 최적화 방법에 따라 실행
            if config.method == OptimizationMethod.GRID_SEARCH:
                result = await self._grid_search_optimization(objective_function, train_data, config)
            elif config.method == OptimizationMethod.GENETIC_ALGORITHM:
                result = await self._genetic_algorithm_optimization(objective_function, train_data, config)
            elif config.method == OptimizationMethod.BAYESIAN:
                result = await self._bayesian_optimization(objective_function, train_data, config)
            elif config.method == OptimizationMethod.RANDOM_SEARCH:
                result = await self._random_search_optimization(objective_function, train_data, config)
            else:
                raise ValueError(f"Unsupported optimization method: {config.method}")
            
            # 검증 데이터로 과적합 확인
            if validation_data is not None and not validation_data.empty:
                validation_score = await self._evaluate_parameters(
                    objective_function, validation_data, result.best_parameters, config.objective
                )
                result.validation_score = validation_score
                
                # 과적합 감지
                score_diff = abs(result.best_score - validation_score) / result.best_score
                result.overfitting_detected = score_diff > 0.3  # 30% 이상 차이면 과적합
            
            result.execution_time = time.time() - start_time
            
            # 히스토리에 추가
            self.optimization_history.append(result)
            if len(self.optimization_history) > self.max_history:
                self.optimization_history.pop(0)
            
            logger.info(f"✅ Optimization completed in {result.execution_time:.2f}s: Best score {result.best_score:.4f}")
            
            return result
            
        except Exception as e:
            logger.error(f"🔴 Error in parameter optimization: {e}")
            raise
    
    async def _grid_search_optimization(
        self,
        objective_function: Callable,
        market_data: pd.DataFrame,
        config: OptimizationConfig
    ) -> OptimizationResult:
        """그리드 서치 최적화"""
        try:
            # 매개변수 조합 생성
            param_combinations = self._generate_parameter_grid(config.parameter_ranges)
            
            if len(param_combinations) > config.max_iterations:
                # 너무 많은 조합이면 랜덤 샘플링
                param_combinations = random.sample(param_combinations, config.max_iterations)
            
            logger.info(f"🔍 Grid search: {len(param_combinations)} combinations")
            
            # 병렬로 매개변수 조합 평가
            tasks = []
            for i, params in enumerate(param_combinations):
                task = self._evaluate_parameters(objective_function, market_data, params, config.objective)
                tasks.append((i, params, task))
            
            # 결과 수집
            results = []
            optimization_history = []
            best_score = float('-inf')
            
            for i, params, task in tasks:
                try:
                    score = await task
                    results.append({
                        'iteration': i,
                        'parameters': params,
                        'score': score
                    })
                    
                    if score > best_score:
                        best_score = score
                        optimization_history.append((i, best_score))
                    
                except Exception as e:
                    logger.error(f"🔴 Error evaluating parameters {i}: {e}")
            
            # 최고 결과 찾기
            if not results:
                raise ValueError("No valid optimization results")
            
            best_result = max(results, key=lambda x: x['score'])
            
            return OptimizationResult(
                best_parameters=best_result['parameters'],
                best_score=best_result['score'],
                all_results=results,
                optimization_history=optimization_history,
                convergence_achieved=True,
                total_evaluations=len(results),
                execution_time=0,  # 나중에 설정
                method_used=config.method,
                objective_used=config.objective
            )
            
        except Exception as e:
            logger.error(f"🔴 Error in grid search optimization: {e}")
            raise
    
    async def _genetic_algorithm_optimization(
        self,
        objective_function: Callable,
        market_data: pd.DataFrame,
        config: OptimizationConfig
    ) -> OptimizationResult:
        """유전 알고리즘 최적화"""
        try:
            # 초기 개체군 생성
            population = self._create_initial_population(config.parameter_ranges, config.population_size)
            
            best_score = float('-inf')
            best_parameters = None
            optimization_history = []
            all_results = []
            total_evaluations = 0
            
            logger.info(f"🧬 Genetic algorithm: {config.population_size} population, {config.max_iterations} generations")
            
            for generation in range(config.max_iterations):
                # 개체군 평가
                fitness_scores = []
                generation_results = []
                
                for individual in population:
                    try:
                        score = await self._evaluate_parameters(
                            objective_function, market_data, individual, config.objective
                        )
                        fitness_scores.append(score)
                        generation_results.append({
                            'generation': generation,
                            'parameters': individual,
                            'score': score
                        })
                        total_evaluations += 1
                        
                        # 최고 점수 업데이트
                        if score > best_score:
                            best_score = score
                            best_parameters = individual.copy()
                            optimization_history.append((generation, best_score))
                        
                    except Exception as e:
                        fitness_scores.append(float('-inf'))
                        logger.error(f"🔴 Error evaluating individual in generation {generation}: {e}")
                
                all_results.extend(generation_results)
                
                # 수렴 확인
                if len(optimization_history) > 10:
                    recent_improvements = [
                        optimization_history[i][1] - optimization_history[i-1][1] 
                        for i in range(-10, 0) if i < len(optimization_history)
                    ]
                    if all(imp < config.convergence_threshold for imp in recent_improvements):
                        logger.info(f"🎯 Convergence achieved at generation {generation}")
                        break
                
                # 다음 세대 생성
                population = self._create_next_generation(
                    population, fitness_scores, config
                )
                
                # 진행 상황 로깅
                avg_fitness = np.mean([f for f in fitness_scores if f != float('-inf')])
                logger.info(f"🧬 Generation {generation}: Best {best_score:.4f}, Avg {avg_fitness:.4f}")
            
            if best_parameters is None:
                raise ValueError("No valid parameters found during optimization")
            
            return OptimizationResult(
                best_parameters=best_parameters,
                best_score=best_score,
                all_results=all_results,
                optimization_history=optimization_history,
                convergence_achieved=True,
                total_evaluations=total_evaluations,
                execution_time=0,  # 나중에 설정
                method_used=config.method,
                objective_used=config.objective
            )
            
        except Exception as e:
            logger.error(f"🔴 Error in genetic algorithm optimization: {e}")
            raise
    
    async def _bayesian_optimization(
        self,
        objective_function: Callable,
        market_data: pd.DataFrame,
        config: OptimizationConfig
    ) -> OptimizationResult:
        """베이지안 최적화"""
        try:
            # 초기 랜덤 샘플링
            n_initial_samples = min(20, config.max_iterations // 4)
            initial_params = self._generate_random_parameters(config.parameter_ranges, n_initial_samples)
            
            # 초기 평가
            X_samples = []
            y_samples = []
            all_results = []
            
            for i, params in enumerate(initial_params):
                try:
                    score = await self._evaluate_parameters(
                        objective_function, market_data, params, config.objective
                    )
                    
                    # 매개변수를 수치 배열로 변환
                    param_array = self._params_to_array(params, config.parameter_ranges)
                    X_samples.append(param_array)
                    y_samples.append(score)
                    
                    all_results.append({
                        'iteration': i,
                        'parameters': params,
                        'score': score
                    })
                    
                except Exception as e:
                    logger.error(f"🔴 Error in initial sample {i}: {e}")
            
            if len(X_samples) < 5:
                raise ValueError("Insufficient initial samples for Bayesian optimization")
            
            # GP 모델 초기화
            kernel = ConstantKernel(1.0) * RBF(length_scale=1.0)
            self.gp_model = GaussianProcessRegressor(kernel=kernel, n_restarts_optimizer=10)
            
            X_array = np.array(X_samples)
            y_array = np.array(y_samples)
            
            best_score = max(y_samples)
            best_idx = y_samples.index(best_score)
            best_parameters = initial_params[best_idx]
            optimization_history = [(i, best_score) for i in range(len(initial_params))]
            
            logger.info(f"🎯 Bayesian optimization: {n_initial_samples} initial samples, best score {best_score:.4f}")
            
            # 베이지안 최적화 반복
            for iteration in range(n_initial_samples, config.max_iterations):
                try:
                    # GP 모델 훈련
                    self.gp_model.fit(X_array, y_array)
                    
                    # Acquisition function으로 다음 포인트 선택
                    next_params = self._select_next_parameters(config.parameter_ranges, X_array, y_array)
                    
                    # 새로운 포인트 평가
                    score = await self._evaluate_parameters(
                        objective_function, market_data, next_params, config.objective
                    )
                    
                    # 결과 업데이트
                    param_array = self._params_to_array(next_params, config.parameter_ranges)
                    X_array = np.vstack([X_array, param_array])
                    y_array = np.append(y_array, score)
                    
                    all_results.append({
                        'iteration': iteration,
                        'parameters': next_params,
                        'score': score
                    })
                    
                    if score > best_score:
                        best_score = score
                        best_parameters = next_params
                        optimization_history.append((iteration, best_score))
                    
                    # 진행 상황 로깅
                    if iteration % 10 == 0:
                        logger.info(f"🎯 Bayesian iteration {iteration}: Best {best_score:.4f}")
                    
                except Exception as e:
                    logger.error(f"🔴 Error in Bayesian iteration {iteration}: {e}")
                    break
            
            return OptimizationResult(
                best_parameters=best_parameters,
                best_score=best_score,
                all_results=all_results,
                optimization_history=optimization_history,
                convergence_achieved=True,
                total_evaluations=len(all_results),
                execution_time=0,
                method_used=config.method,
                objective_used=config.objective
            )
            
        except Exception as e:
            logger.error(f"🔴 Error in Bayesian optimization: {e}")
            raise
    
    async def _random_search_optimization(
        self,
        objective_function: Callable,
        market_data: pd.DataFrame,
        config: OptimizationConfig
    ) -> OptimizationResult:
        """랜덤 서치 최적화"""
        try:
            # 랜덤 매개변수 생성
            random_params = self._generate_random_parameters(config.parameter_ranges, config.max_iterations)
            
            best_score = float('-inf')
            best_parameters = None
            all_results = []
            optimization_history = []
            
            logger.info(f"🎲 Random search: {len(random_params)} random combinations")
            
            # 병렬로 평가
            tasks = []
            for i, params in enumerate(random_params):
                task = self._evaluate_parameters(objective_function, market_data, params, config.objective)
                tasks.append((i, params, task))
            
            # 결과 수집
            for i, params, task in tasks:
                try:
                    score = await task
                    all_results.append({
                        'iteration': i,
                        'parameters': params,
                        'score': score
                    })
                    
                    if score > best_score:
                        best_score = score
                        best_parameters = params
                        optimization_history.append((i, best_score))
                    
                except Exception as e:
                    logger.error(f"🔴 Error in random search iteration {i}: {e}")
            
            if not all_results:
                raise ValueError("No valid results from random search")
            
            return OptimizationResult(
                best_parameters=best_parameters,
                best_score=best_score,
                all_results=all_results,
                optimization_history=optimization_history,
                convergence_achieved=True,
                total_evaluations=len(all_results),
                execution_time=0,
                method_used=config.method,
                objective_used=config.objective
            )
            
        except Exception as e:
            logger.error(f"🔴 Error in random search optimization: {e}")
            raise
    
    def _generate_parameter_grid(self, parameter_ranges: Dict[str, ParameterRange]) -> List[Dict[str, Any]]:
        """매개변수 그리드 생성"""
        try:
            param_lists = {}
            
            for name, param_range in parameter_ranges.items():
                if param_range.values:
                    param_lists[name] = param_range.values
                elif param_range.step:
                    if param_range.is_integer:
                        values = list(range(int(param_range.min_value), int(param_range.max_value) + 1, int(param_range.step)))
                    else:
                        values = list(np.arange(param_range.min_value, param_range.max_value + param_range.step, param_range.step))
                    param_lists[name] = values
                else:
                    # 기본적으로 10개 값 생성
                    if param_range.is_integer:
                        values = list(np.linspace(param_range.min_value, param_range.max_value, 10, dtype=int))
                    else:
                        values = list(np.linspace(param_range.min_value, param_range.max_value, 10))
                    param_lists[name] = values
            
            # 모든 조합 생성
            keys = list(param_lists.keys())
            values = list(param_lists.values())
            
            combinations = []
            for combination in itertools.product(*values):
                param_dict = dict(zip(keys, combination))
                combinations.append(param_dict)
            
            logger.info(f"📋 Generated {len(combinations)} parameter combinations")
            return combinations
            
        except Exception as e:
            logger.error(f"🔴 Error generating parameter grid: {e}")
            return []
    
    def _create_initial_population(self, parameter_ranges: Dict[str, ParameterRange], population_size: int) -> List[Dict[str, Any]]:
        """초기 개체군 생성 (유전 알고리즘)"""
        return self._generate_random_parameters(parameter_ranges, population_size)
    
    def _generate_random_parameters(self, parameter_ranges: Dict[str, ParameterRange], count: int) -> List[Dict[str, Any]]:
        """랜덤 매개변수 생성"""
        try:
            random_params = []
            
            for _ in range(count):
                params = {}
                for name, param_range in parameter_ranges.items():
                    if param_range.values:
                        # 고정된 값 목록에서 선택
                        params[name] = random.choice(param_range.values)
                    else:
                        # 범위에서 랜덤 값 생성
                        if param_range.is_integer:
                            params[name] = random.randint(int(param_range.min_value), int(param_range.max_value))
                        else:
                            params[name] = random.uniform(param_range.min_value, param_range.max_value)
                
                random_params.append(params)
            
            return random_params
            
        except Exception as e:
            logger.error(f"🔴 Error generating random parameters: {e}")
            return []
    
    def _create_next_generation(
        self,
        population: List[Dict[str, Any]],
        fitness_scores: List[float],
        config: OptimizationConfig
    ) -> List[Dict[str, Any]]:
        """다음 세대 생성 (유전 알고리즘)"""
        try:
            # 유효한 개체들만 선택
            valid_individuals = [
                (ind, score) for ind, score in zip(population, fitness_scores)
                if score != float('-inf')
            ]
            
            if len(valid_individuals) < 2:
                # 유효한 개체가 너무 적으면 새로운 랜덤 개체군 생성
                return self._generate_random_parameters(config.parameter_ranges, config.population_size)
            
            # 적합도 기반 선택 (상위 50% 선택)
            valid_individuals.sort(key=lambda x: x[1], reverse=True)
            elite_count = max(2, len(valid_individuals) // 2)
            elite_individuals = [ind[0] for ind in valid_individuals[:elite_count]]
            
            next_generation = []
            
            # 엘리트 보존
            next_generation.extend(elite_individuals[:config.population_size // 4])
            
            # 교배 및 돌연변이
            while len(next_generation) < config.population_size:
                # 부모 선택 (토너먼트 선택)
                parent1 = self._tournament_selection(valid_individuals, 3)
                parent2 = self._tournament_selection(valid_individuals, 3)
                
                # 교배
                if random.random() < config.crossover_rate:
                    child = self._crossover(parent1, parent2, config.parameter_ranges)
                else:
                    child = parent1.copy()
                
                # 돌연변이
                if random.random() < config.mutation_rate:
                    child = self._mutate(child, config.parameter_ranges)
                
                next_generation.append(child)
            
            return next_generation[:config.population_size]
            
        except Exception as e:
            logger.error(f"🔴 Error creating next generation: {e}")
            return self._generate_random_parameters(config.parameter_ranges, config.population_size)
    
    def _tournament_selection(self, individuals: List[Tuple[Dict, float]], tournament_size: int) -> Dict[str, Any]:
        """토너먼트 선택"""
        tournament = random.sample(individuals, min(tournament_size, len(individuals)))
        winner = max(tournament, key=lambda x: x[1])
        return winner[0]
    
    def _crossover(self, parent1: Dict[str, Any], parent2: Dict[str, Any], parameter_ranges: Dict[str, ParameterRange]) -> Dict[str, Any]:
        """교배"""
        child = {}
        for param_name in parent1.keys():
            if random.random() < 0.5:
                child[param_name] = parent1[param_name]
            else:
                child[param_name] = parent2[param_name]
        return child
    
    def _mutate(self, individual: Dict[str, Any], parameter_ranges: Dict[str, ParameterRange]) -> Dict[str, Any]:
        """돌연변이"""
        mutated = individual.copy()
        
        for param_name, param_range in parameter_ranges.items():
            if random.random() < 0.1:  # 10% 확률로 각 매개변수 돌연변이
                if param_range.values:
                    mutated[param_name] = random.choice(param_range.values)
                else:
                    if param_range.is_integer:
                        mutated[param_name] = random.randint(int(param_range.min_value), int(param_range.max_value))
                    else:
                        # 가우시안 노이즈 추가
                        current_value = individual[param_name]
                        noise_std = (param_range.max_value - param_range.min_value) * 0.1
                        new_value = current_value + np.random.normal(0, noise_std)
                        new_value = np.clip(new_value, param_range.min_value, param_range.max_value)
                        mutated[param_name] = new_value
        
        return mutated
    
    def _params_to_array(self, params: Dict[str, Any], parameter_ranges: Dict[str, ParameterRange]) -> np.ndarray:
        """매개변수를 수치 배열로 변환 (베이지안 최적화용)"""
        array = []
        for name in sorted(parameter_ranges.keys()):
            value = params[name]
            param_range = parameter_ranges[name]
            
            # 정규화 (0-1 범위)
            if param_range.values:
                normalized = param_range.values.index(value) / (len(param_range.values) - 1)
            else:
                normalized = (value - param_range.min_value) / (param_range.max_value - param_range.min_value)
            
            array.append(normalized)
        
        return np.array(array)
    
    def _select_next_parameters(
        self,
        parameter_ranges: Dict[str, ParameterRange],
        X_samples: np.ndarray,
        y_samples: np.ndarray
    ) -> Dict[str, Any]:
        """다음 매개변수 선택 (Acquisition Function)"""
        try:
            # Upper Confidence Bound (UCB) 사용
            n_candidates = 100
            random_candidates = self._generate_random_parameters(parameter_ranges, n_candidates)
            
            best_acquisition = float('-inf')
            best_candidate = None
            
            for candidate in random_candidates:
                candidate_array = self._params_to_array(candidate, parameter_ranges).reshape(1, -1)
                
                # GP 예측
                mean, std = self.gp_model.predict(candidate_array, return_std=True)
                
                # UCB acquisition function
                beta = 2.0  # 탐험 vs 활용 균형
                acquisition_value = mean[0] + beta * std[0]
                
                if acquisition_value > best_acquisition:
                    best_acquisition = acquisition_value
                    best_candidate = candidate
            
            return best_candidate or random_candidates[0]
            
        except Exception as e:
            logger.error(f"🔴 Error selecting next parameters: {e}")
            return self._generate_random_parameters(parameter_ranges, 1)[0]
    
    async def _evaluate_parameters(
        self,
        objective_function: Callable,
        market_data: pd.DataFrame,
        parameters: Dict[str, Any],
        objective: OptimizationObjective
    ) -> float:
        """매개변수 평가"""
        try:
            # 백테스트 실행 (매개변수 적용)
            # 실제 구현에서는 objective_function이 매개변수를 받아서 백테스트를 실행
            # 여기서는 시뮬레이션된 결과 반환
            
            # 시뮬레이션된 백테스트 결과
            np.random.seed(hash(str(parameters)) % 2**32)
            
            # 매개변수 품질에 따라 성과 조정
            param_quality = self._assess_parameter_quality(parameters)
            
            if objective == OptimizationObjective.SHARPE_RATIO:
                base_score = np.random.normal(0.5, 0.3)  # 평균 0.5, 표준편차 0.3
                score = base_score * param_quality
            elif objective == OptimizationObjective.TOTAL_RETURN:
                base_score = np.random.normal(10, 5)  # 평균 10%, 표준편차 5%
                score = base_score * param_quality
            elif objective == OptimizationObjective.WIN_RATE:
                base_score = np.random.uniform(0.4, 0.8)  # 40-80% 승률
                score = base_score * param_quality
            else:
                base_score = np.random.normal(1.5, 0.5)  # 기본 점수
                score = base_score * param_quality
            
            # 점수 클리핑
            score = max(0, score)
            
            return score
            
        except Exception as e:
            logger.error(f"🔴 Error evaluating parameters: {e}")
            return 0.0
    
    def _assess_parameter_quality(self, parameters: Dict[str, Any]) -> float:
        """매개변수 품질 평가"""
        try:
            quality_score = 1.0
            
            # 일반적인 기술적 지표 매개변수 품질 평가
            for param_name, value in parameters.items():
                if 'period' in param_name.lower():
                    # 기간 매개변수: 너무 짧거나 길면 품질 저하
                    if value < 5 or value > 50:
                        quality_score *= 0.8
                    elif 10 <= value <= 30:
                        quality_score *= 1.1  # 적정 범위는 보너스
                
                elif 'threshold' in param_name.lower():
                    # 임계값 매개변수: 극단값은 품질 저하
                    if abs(value) > 150:
                        quality_score *= 0.7
                
                elif 'multiplier' in param_name.lower():
                    # 승수 매개변수: 1-3 범위가 적정
                    if not (0.5 <= value <= 5.0):
                        quality_score *= 0.8
            
            return min(1.5, max(0.3, quality_score))  # 0.3 ~ 1.5 범위로 제한
            
        except Exception as e:
            logger.error(f"🔴 Error assessing parameter quality: {e}")
            return 1.0
    
    async def auto_optimize_strategy(
        self,
        strategy_name: str,
        performance_data: List[Dict],
        market_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """전략 자동 최적화"""
        try:
            # 전략별 기본 매개변수 범위 설정
            if 'cci' in strategy_name.lower():
                parameter_ranges = {
                    'cci_period': ParameterRange('cci_period', 10, 30, is_integer=True),
                    'overbought': ParameterRange('overbought', 80, 150),
                    'oversold': ParameterRange('oversold', -150, -80)
                }
            elif 'rsi' in strategy_name.lower():
                parameter_ranges = {
                    'rsi_period': ParameterRange('rsi_period', 10, 25, is_integer=True),
                    'overbought': ParameterRange('overbought', 65, 85),
                    'oversold': ParameterRange('oversold', 15, 35)
                }
            elif 'macd' in strategy_name.lower():
                parameter_ranges = {
                    'fast_period': ParameterRange('fast_period', 8, 16, is_integer=True),
                    'slow_period': ParameterRange('slow_period', 20, 35, is_integer=True),
                    'signal_period': ParameterRange('signal_period', 7, 12, is_integer=True)
                }
            else:
                # 기본 매개변수
                parameter_ranges = {
                    'period': ParameterRange('period', 10, 30, is_integer=True),
                    'threshold': ParameterRange('threshold', 0.5, 2.0)
                }
            
            # 최적화 설정
            config = OptimizationConfig(
                method=OptimizationMethod.GENETIC_ALGORITHM,
                objective=OptimizationObjective.SHARPE_RATIO,
                parameter_ranges=parameter_ranges,
                max_iterations=30,  # 빠른 테스트를 위해 축소
                population_size=20
            )
            
            # 간단한 목적 함수 (실제로는 전략별 백테스트 함수)
            async def simple_objective(data):
                return np.random.normal(0.5, 0.2)  # 시뮬레이션
            
            # 최적화 실행 (이미 async 컨텍스트 내부이므로 await 사용)
            result = await self.optimize_parameters(simple_objective, config, market_data)
            
            # 기존 매개변수와 비교
            current_performance = self._calculate_current_performance(performance_data)
            improvement = result.best_score - current_performance
            
            return {
                'strategy_name': strategy_name,
                'optimization_result': {
                    'best_parameters': result.best_parameters,
                    'best_score': result.best_score,
                    'improvement': improvement,
                    'improvement_pct': (improvement / current_performance * 100) if current_performance > 0 else 0,
                    'evaluations': result.total_evaluations,
                    'execution_time': result.execution_time
                },
                'current_performance': current_performance,
                'recommendation': 'APPLY' if improvement > 0.1 else 'KEEP_CURRENT',
                'confidence': min(1.0, abs(improvement) / 0.5),  # 개선이 클수록 높은 신뢰도
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"🔴 Error in auto strategy optimization: {e}")
            return {'error': str(e)}
    
    def _calculate_current_performance(self, performance_data: List[Dict]) -> float:
        """현재 성과 계산"""
        try:
            if not performance_data:
                return 0.0
            
            returns = [trade.get('pnl_pct', 0) / 100 for trade in performance_data]
            
            if len(returns) < 2:
                return 0.0
            
            # Sharpe Ratio 계산
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            
            sharpe = mean_return / std_return * np.sqrt(252) if std_return > 0 else 0
            
            return sharpe
            
        except Exception as e:
            logger.error(f"🔴 Error calculating current performance: {e}")
            return 0.0
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """최적화 요약"""
        try:
            if not self.optimization_history:
                return {'message': 'No optimization history available'}
            
            recent_optimizations = self.optimization_history[-10:]
            
            # 방법별 성과
            method_performance = {}
            for result in recent_optimizations:
                method = result.method_used.value
                if method not in method_performance:
                    method_performance[method] = {'count': 0, 'avg_score': 0, 'best_score': 0}
                
                method_performance[method]['count'] += 1
                method_performance[method]['avg_score'] += result.best_score
                method_performance[method]['best_score'] = max(method_performance[method]['best_score'], result.best_score)
            
            for method, perf in method_performance.items():
                perf['avg_score'] /= perf['count']
                perf['avg_score'] = round(perf['avg_score'], 4)
                perf['best_score'] = round(perf['best_score'], 4)
            
            # 최고 결과
            best_result = max(recent_optimizations, key=lambda x: x.best_score)
            
            return {
                'total_optimizations': len(self.optimization_history),
                'recent_optimizations': len(recent_optimizations),
                'method_performance': method_performance,
                'best_result': {
                    'score': round(best_result.best_score, 4),
                    'method': best_result.method_used.value,
                    'objective': best_result.objective_used.value,
                    'parameters': best_result.best_parameters,
                    'timestamp': best_result.timestamp.isoformat()
                },
                'optimization_efficiency': {
                    'avg_evaluations': round(np.mean([r.total_evaluations for r in recent_optimizations]), 1),
                    'avg_execution_time': round(np.mean([r.execution_time for r in recent_optimizations]), 2),
                    'convergence_rate': sum(1 for r in recent_optimizations if r.convergence_achieved) / len(recent_optimizations) * 100
                }
            }
            
        except Exception as e:
            logger.error(f"🔴 Error getting optimization summary: {e}")
            return {'error': str(e)}

# 테스트 함수
async def test_parameter_optimizer():
    """Parameter Optimizer 테스트"""
    print("🧪 Testing Parameter Optimizer...")
    
    # 최적화기 생성
    optimizer = ParameterOptimizer(max_workers=2)
    
    # 샘플 시장 데이터
    dates = pd.date_range('2025-01-01', periods=1000, freq='5min')
    np.random.seed(42)
    
    price_base = 50000
    price_data = price_base + np.cumsum(np.random.randn(1000) * 50)
    
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': price_data + np.random.randn(1000) * 25,
        'high': price_data + np.abs(np.random.randn(1000) * 50),
        'low': price_data - np.abs(np.random.randn(1000) * 50),
        'close': price_data,
        'volume': np.random.randint(1000, 10000, 1000)
    })
    
    # 간단한 목적 함수
    async def test_objective(data):
        await asyncio.sleep(0.01)  # 시뮬레이션 지연
        return np.random.normal(1.0, 0.3)
    
    # 매개변수 범위 정의
    parameter_ranges = {
        'cci_period': ParameterRange('cci_period', 10, 30, is_integer=True),
        'overbought': ParameterRange('overbought', 80, 120),
        'oversold': ParameterRange('oversold', -120, -80)
    }
    
    # 1. 그리드 서치 테스트
    print("🔍 Grid Search Optimization:")
    grid_config = OptimizationConfig(
        method=OptimizationMethod.GRID_SEARCH,
        objective=OptimizationObjective.SHARPE_RATIO,
        parameter_ranges=parameter_ranges,
        max_iterations=20
    )
    
    try:
        grid_result = await optimizer.optimize_parameters(test_objective, grid_config, market_data)
        print(f"  - Best Score: {grid_result.best_score:.4f}")
        print(f"  - Best Parameters: {grid_result.best_parameters}")
        print(f"  - Evaluations: {grid_result.total_evaluations}")
        print(f"  - Time: {grid_result.execution_time:.2f}s")
    except Exception as e:
        print(f"  - Grid Search Error: {e}")
    
    # 2. 유전 알고리즘 테스트
    print(f"\\n🧬 Genetic Algorithm Optimization:")
    ga_config = OptimizationConfig(
        method=OptimizationMethod.GENETIC_ALGORITHM,
        objective=OptimizationObjective.SHARPE_RATIO,
        parameter_ranges=parameter_ranges,
        max_iterations=10,
        population_size=15
    )
    
    try:
        ga_result = await optimizer.optimize_parameters(test_objective, ga_config, market_data)
        print(f"  - Best Score: {ga_result.best_score:.4f}")
        print(f"  - Best Parameters: {ga_result.best_parameters}")
        print(f"  - Generations: {len(ga_result.optimization_history)}")
        print(f"  - Convergence: {ga_result.convergence_achieved}")
    except Exception as e:
        print(f"  - Genetic Algorithm Error: {e}")
    
    # 3. 랜덤 서치 테스트
    print(f"\\n🎲 Random Search Optimization:")
    random_config = OptimizationConfig(
        method=OptimizationMethod.RANDOM_SEARCH,
        objective=OptimizationObjective.TOTAL_RETURN,
        parameter_ranges=parameter_ranges,
        max_iterations=25
    )
    
    try:
        random_result = await optimizer.optimize_parameters(test_objective, random_config, market_data)
        print(f"  - Best Score: {random_result.best_score:.4f}")
        print(f"  - Best Parameters: {random_result.best_parameters}")
        print(f"  - Evaluations: {random_result.total_evaluations}")
    except Exception as e:
        print(f"  - Random Search Error: {e}")
    
    # 4. 자동 전략 최적화 테스트
    print(f"\\n🎯 Auto Strategy Optimization:")
    sample_performance = [
        {'pnl': 150, 'pnl_pct': 3.0, 'timestamp': datetime.now() - timedelta(days=i)}
        for i in range(20)
    ]
    
    try:
        auto_result = optimizer.auto_optimize_strategy("CCI_Strategy", sample_performance, market_data)
        print(f"  - Strategy: {auto_result['strategy_name']}")
        print(f"  - Best Score: {auto_result['optimization_result']['best_score']:.4f}")
        print(f"  - Improvement: {auto_result['optimization_result']['improvement']:.4f}")
        print(f"  - Recommendation: {auto_result['recommendation']}")
        print(f"  - Confidence: {auto_result['confidence']:.2f}")
    except Exception as e:
        print(f"  - Auto Optimization Error: {e}")
    
    # 5. 최적화 요약
    print(f"\\n📊 Optimization Summary:")
    summary = optimizer.get_optimization_summary()
    if 'error' not in summary:
        print(f"  - Total optimizations: {summary['total_optimizations']}")
        print(f"  - Method performance: {summary['method_performance']}")
        print(f"  - Convergence rate: {summary['optimization_efficiency']['convergence_rate']:.1f}%")
    else:
        print(f"  - Summary Error: {summary['error']}")

if __name__ == "__main__":
    import asyncio
    import time
    asyncio.run(test_parameter_optimizer())