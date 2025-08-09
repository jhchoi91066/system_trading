"""
데모 트레이딩 시뮬레이터
- 실제 자금 없이 거래 전략 테스트
- 실거래와 동일한 API 인터페이스 제공
- 가상 잔고 및 포지션 관리
- 실시간 시장 데이터 기반 시뮬레이션
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import uuid
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    PARTIALLY_FILLED = "partially_filled"

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"

@dataclass
class DemoBalance:
    """데모 계정 잔고"""
    currency: str
    total: float
    available: float
    locked: float = 0.0
    
    def lock_amount(self, amount: float) -> bool:
        """금액 잠금"""
        if self.available >= amount:
            self.available -= amount
            self.locked += amount
            return True
        return False
    
    def unlock_amount(self, amount: float):
        """금액 잠금 해제"""
        unlock_amount = min(amount, self.locked)
        self.locked -= unlock_amount
        self.available += unlock_amount
    
    def add_amount(self, amount: float):
        """잔고 추가"""
        self.available += amount
        self.total += amount
    
    def subtract_amount(self, amount: float) -> bool:
        """잔고 차감"""
        if self.available >= amount:
            self.available -= amount
            self.total -= amount
            return True
        return False

@dataclass
class DemoOrder:
    """데모 주문"""
    id: str
    user_id: str
    exchange: str
    symbol: str
    side: str  # 'buy' or 'sell'
    order_type: OrderType
    amount: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_amount: float = 0.0
    remaining_amount: float = field(init=False)
    average_price: float = 0.0
    fee: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    fills: List[Dict] = field(default_factory=list)
    
    def __post_init__(self):
        self.remaining_amount = self.amount
    
    def add_fill(self, quantity: float, price: float, fee: float = 0.0):
        """체결 추가"""
        self.fills.append({
            'quantity': quantity,
            'price': price,
            'fee': fee,
            'timestamp': datetime.now()
        })
        
        self.filled_amount += quantity
        self.remaining_amount = self.amount - self.filled_amount
        
        # 평균 체결가 계산
        total_value = sum(fill['quantity'] * fill['price'] for fill in self.fills)
        self.average_price = total_value / self.filled_amount if self.filled_amount > 0 else 0
        
        # 수수료 누적
        self.fee += fee
        
        # 상태 업데이트
        if self.remaining_amount <= 0:
            self.status = OrderStatus.FILLED
        elif self.filled_amount > 0:
            self.status = OrderStatus.PARTIALLY_FILLED
        
        self.updated_at = datetime.now()

@dataclass
class DemoPosition:
    """데모 포지션"""
    id: str
    user_id: str
    exchange: str
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def update_price(self, price: float):
        """현재가 업데이트 및 미실현 손익 계산"""
        self.current_price = price
        
        if self.side == 'long':
            self.unrealized_pnl = (price - self.entry_price) * self.size
        else:  # short
            self.unrealized_pnl = (self.entry_price - price) * self.size
        
        self.updated_at = datetime.now()
    
    def check_stop_conditions(self) -> Optional[str]:
        """손절/익절 조건 확인"""
        if not self.current_price:
            return None
        
        if self.side == 'long':
            if self.stop_loss and self.current_price <= self.stop_loss:
                return "stop_loss"
            if self.take_profit and self.current_price >= self.take_profit:
                return "take_profit"
        else:  # short
            if self.stop_loss and self.current_price >= self.stop_loss:
                return "stop_loss"
            if self.take_profit and self.current_price <= self.take_profit:
                return "take_profit"
        
        return None

class DemoTradingSimulator:
    """데모 트레이딩 시뮬레이터"""
    
    def __init__(self, initial_balance: float = 10000.0, base_currency: str = "USDT"):
        self.balances: Dict[str, Dict[str, DemoBalance]] = {}  # user_id -> currency -> balance
        self.orders: Dict[str, DemoOrder] = {}  # order_id -> order
        self.positions: Dict[str, DemoPosition] = {}  # position_id -> position
        self.trades: List[Dict] = []  # 거래 기록
        
        self.initial_balance = initial_balance
        self.base_currency = base_currency
        
        # 수수료 설정
        self.maker_fee = 0.001  # 0.1%
        self.taker_fee = 0.001  # 0.1%
        
        # 슬리피지 설정
        self.slippage_rate = 0.0005  # 0.05%
        
        # 실행 지연 시뮬레이션
        self.execution_delay = 0.1  # 100ms
        
        logger.info("Demo Trading Simulator initialized")
    
    def initialize_user_balance(self, user_id: str, balance: float = None) -> bool:
        """사용자 잔고 초기화"""
        try:
            if balance is None:
                balance = self.initial_balance
            
            if user_id not in self.balances:
                self.balances[user_id] = {}
            
            self.balances[user_id][self.base_currency] = DemoBalance(
                currency=self.base_currency,
                total=balance,
                available=balance
            )
            
            logger.info(f"Initialized demo balance for user {user_id}: {balance} {self.base_currency}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize user balance: {e}")
            return False
    
    def get_balance(self, user_id: str) -> Dict[str, Any]:
        """잔고 조회"""
        try:
            if user_id not in self.balances:
                self.initialize_user_balance(user_id)
            
            user_balances = self.balances[user_id]
            
            balance_info = {}
            for currency, balance in user_balances.items():
                balance_info[currency] = {
                    'total': balance.total,
                    'available': balance.available,
                    'locked': balance.locked
                }
            
            return balance_info
            
        except Exception as e:
            logger.error(f"Failed to get balance for user {user_id}: {e}")
            return {}
    
    async def place_order(self, user_id: str, exchange: str, symbol: str, side: str, 
                         order_type: str, amount: float, price: float = None, 
                         stop_price: float = None, current_market_price: float = None) -> Dict[str, Any]:
        """주문 생성"""
        try:
            # 사용자 잔고 확인
            if user_id not in self.balances:
                self.initialize_user_balance(user_id)
            
            # 주문 ID 생성
            order_id = str(uuid.uuid4())
            
            # 주문 객체 생성
            order = DemoOrder(
                id=order_id,
                user_id=user_id,
                exchange=exchange,
                symbol=symbol,
                side=side.lower(),
                order_type=OrderType(order_type.lower()),
                amount=amount,
                price=price,
                stop_price=stop_price
            )
            
            # 매수 주문의 경우 필요 자금 잠금
            if side.lower() == 'buy':
                required_amount = amount * (price if price else current_market_price or 0)
                user_balance = self.balances[user_id].get(self.base_currency)
                
                if not user_balance or not user_balance.lock_amount(required_amount):
                    return {'error': 'Insufficient balance'}
            
            # 매도 주문의 경우 보유 포지션 확인 (간단화)
            elif side.lower() == 'sell':
                # 실제로는 보유한 암호화폐 수량을 확인해야 하지만, 여기서는 간단화
                pass
            
            self.orders[order_id] = order
            
            # 시장가 주문의 경우 즉시 체결
            if order_type.lower() == 'market' and current_market_price:
                await self._execute_market_order(order, current_market_price)
            
            # 지정가 주문의 경우 조건부 체결 (별도 스레드에서 모니터링)
            elif order_type.lower() == 'limit':
                asyncio.create_task(self._monitor_limit_order(order))
            
            return {
                'id': order_id,
                'status': order.status.value,
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'price': price,
                'timestamp': order.created_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return {'error': str(e)}
    
    async def _execute_market_order(self, order: DemoOrder, market_price: float):
        """시장가 주문 체결"""
        try:
            # 실행 지연 시뮬레이션
            await asyncio.sleep(self.execution_delay)
            
            # 슬리피지 적용
            if order.side == 'buy':
                execution_price = market_price * (1 + self.slippage_rate)
            else:
                execution_price = market_price * (1 - self.slippage_rate)
            
            # 수수료 계산
            fee = order.amount * execution_price * self.taker_fee
            
            # 주문 체결
            order.add_fill(order.amount, execution_price, fee)
            
            # 거래 기록 저장
            await self._record_trade(order, order.amount, execution_price, fee)
            
            # 포지션 업데이트
            await self._update_position(order, order.amount, execution_price)
            
            logger.info(f"Market order executed: {order.id} at {execution_price}")
            
        except Exception as e:
            logger.error(f"Failed to execute market order: {e}")
            order.status = OrderStatus.CANCELLED
    
    async def _monitor_limit_order(self, order: DemoOrder):
        """지정가 주문 모니터링"""
        try:
            # 실제로는 실시간 가격을 모니터링해야 하지만, 여기서는 간단화
            # 실제 구현에서는 WebSocket이나 주기적 가격 확인이 필요
            pass
        except Exception as e:
            logger.error(f"Failed to monitor limit order: {e}")
    
    async def _record_trade(self, order: DemoOrder, quantity: float, price: float, fee: float):
        """거래 기록 저장"""
        try:
            trade_record = {
                'id': str(uuid.uuid4()),
                'user_id': order.user_id,
                'order_id': order.id,
                'exchange': order.exchange,
                'symbol': order.symbol,
                'side': order.side,
                'quantity': quantity,
                'price': price,
                'fee': fee,
                'timestamp': datetime.now().isoformat(),
                'is_demo': True
            }
            
            self.trades.append(trade_record)
            
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
    
    async def _update_position(self, order: DemoOrder, quantity: float, price: float):
        """포지션 업데이트"""
        try:
            position_key = f"{order.user_id}_{order.exchange}_{order.symbol}"
            
            if position_key in self.positions:
                # 기존 포지션 업데이트
                position = self.positions[position_key]
                
                if order.side == 'buy':
                    # 롱 포지션 증가 또는 숏 포지션 감소
                    if position.side == 'long':
                        # 평균 진입가 계산
                        total_value = (position.size * position.entry_price) + (quantity * price)
                        position.size += quantity
                        position.entry_price = total_value / position.size
                    else:  # short position
                        position.size = max(0, position.size - quantity)
                        if position.size == 0:
                            del self.positions[position_key]
                            return
                
                else:  # sell
                    # 롱 포지션 감소 또는 숏 포지션 증가
                    if position.side == 'long':
                        position.size = max(0, position.size - quantity)
                        if position.size == 0:
                            del self.positions[position_key]
                            return
                    else:  # short position
                        total_value = (position.size * position.entry_price) + (quantity * price)
                        position.size += quantity
                        position.entry_price = total_value / position.size
                
                position.updated_at = datetime.now()
            
            else:
                # 새 포지션 생성
                if order.side == 'buy':
                    side = 'long'
                    size = quantity
                else:
                    side = 'short'
                    size = quantity
                
                position = DemoPosition(
                    id=str(uuid.uuid4()),
                    user_id=order.user_id,
                    exchange=order.exchange,
                    symbol=order.symbol,
                    side=side,
                    size=size,
                    entry_price=price
                )
                
                self.positions[position_key] = position
            
        except Exception as e:
            logger.error(f"Failed to update position: {e}")
    
    def get_positions(self, user_id: str, symbol: str = None) -> List[Dict[str, Any]]:
        """포지션 조회"""
        try:
            user_positions = []
            
            for position in self.positions.values():
                if position.user_id == user_id:
                    if symbol is None or position.symbol == symbol:
                        user_positions.append({
                            'id': position.id,
                            'symbol': position.symbol,
                            'side': position.side,
                            'size': position.size,
                            'entry_price': position.entry_price,
                            'current_price': position.current_price,
                            'unrealized_pnl': position.unrealized_pnl,
                            'realized_pnl': position.realized_pnl,
                            'created_at': position.created_at.isoformat()
                        })
            
            return user_positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    def get_orders(self, user_id: str, symbol: str = None, status: str = None) -> List[Dict[str, Any]]:
        """주문 조회"""
        try:
            user_orders = []
            
            for order in self.orders.values():
                if order.user_id == user_id:
                    if symbol is None or order.symbol == symbol:
                        if status is None or order.status.value == status:
                            user_orders.append({
                                'id': order.id,
                                'symbol': order.symbol,
                                'side': order.side,
                                'type': order.order_type.value,
                                'amount': order.amount,
                                'price': order.price,
                                'status': order.status.value,
                                'filled': order.filled_amount,
                                'remaining': order.remaining_amount,
                                'created_at': order.created_at.isoformat()
                            })
            
            return user_orders
            
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    def get_trade_history(self, user_id: str, symbol: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """거래 기록 조회"""
        try:
            user_trades = []
            
            for trade in reversed(self.trades):  # 최신 순으로
                if trade['user_id'] == user_id:
                    if symbol is None or trade['symbol'] == symbol:
                        user_trades.append(trade)
                        if len(user_trades) >= limit:
                            break
            
            return user_trades
            
        except Exception as e:
            logger.error(f"Failed to get trade history: {e}")
            return []
    
    async def cancel_order(self, user_id: str, order_id: str) -> Dict[str, Any]:
        """주문 취소"""
        try:
            if order_id not in self.orders:
                return {'error': 'Order not found'}
            
            order = self.orders[order_id]
            
            if order.user_id != user_id:
                return {'error': 'Unauthorized'}
            
            if order.status == OrderStatus.FILLED:
                return {'error': 'Order already filled'}
            
            if order.status == OrderStatus.CANCELLED:
                return {'error': 'Order already cancelled'}
            
            # 잠금된 자금 해제
            if order.side == 'buy' and order.price:
                locked_amount = (order.amount - order.filled_amount) * order.price
                user_balance = self.balances[user_id].get(self.base_currency)
                if user_balance:
                    user_balance.unlock_amount(locked_amount)
            
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now()
            
            return {
                'id': order_id,
                'status': 'cancelled',
                'message': 'Order cancelled successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return {'error': str(e)}
    
    def update_market_prices(self, prices: Dict[str, float]):
        """시장 가격 업데이트 (포지션 PnL 계산용)"""
        try:
            for position in self.positions.values():
                if position.symbol in prices:
                    position.update_price(prices[position.symbol])
                    
                    # 손절/익절 조건 확인
                    trigger = position.check_stop_conditions()
                    if trigger:
                        # 자동 청산 (비동기로 처리)
                        asyncio.create_task(self._auto_close_position(position, trigger))
                        
        except Exception as e:
            logger.error(f"Failed to update market prices: {e}")
    
    async def _auto_close_position(self, position: DemoPosition, reason: str):
        """포지션 자동 청산"""
        try:
            # 반대 방향 시장가 주문으로 청산
            close_side = 'sell' if position.side == 'long' else 'buy'
            
            await self.place_order(
                user_id=position.user_id,
                exchange=position.exchange,
                symbol=position.symbol,
                side=close_side,
                order_type='market',
                amount=position.size,
                current_market_price=position.current_price
            )
            
            logger.info(f"Position auto-closed: {position.id} due to {reason}")
            
        except Exception as e:
            logger.error(f"Failed to auto-close position: {e}")
    
    def get_performance_summary(self, user_id: str) -> Dict[str, Any]:
        """성과 요약"""
        try:
            user_trades = self.get_trade_history(user_id)
            user_positions = self.get_positions(user_id)
            balance = self.get_balance(user_id)
            
            # 실현 손익 계산
            realized_pnl = 0.0
            total_fees = 0.0
            
            for trade in user_trades:
                if trade['side'] == 'sell':
                    # 매도 시 실현 손익 계산 (간단화)
                    pass
                total_fees += trade.get('fee', 0)
            
            # 미실현 손익 계산
            unrealized_pnl = sum(pos['unrealized_pnl'] for pos in user_positions)
            
            # 총 자산 가치
            total_balance = balance.get(self.base_currency, {}).get('total', 0)
            total_value = total_balance + unrealized_pnl
            
            # 수익률 계산
            total_return = ((total_value - self.initial_balance) / self.initial_balance) * 100
            
            return {
                'initial_balance': self.initial_balance,
                'current_balance': total_balance,
                'total_value': total_value,
                'realized_pnl': realized_pnl,
                'unrealized_pnl': unrealized_pnl,
                'total_fees': total_fees,
                'total_return': total_return,
                'total_trades': len(user_trades),
                'open_positions': len(user_positions)
            }
            
        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {}

# 글로벌 시뮬레이터 인스턴스
demo_simulator = DemoTradingSimulator()

# ============= 유틸리티 함수 =============

def is_demo_mode_enabled(user_id: str) -> bool:
    """사용자의 데모 모드 활성화 여부 확인"""
    # 실제로는 데이터베이스에서 사용자 설정을 확인
    return False  # 임시로 항상 False 반환

def switch_trading_mode(user_id: str, demo_mode: bool) -> bool:
    """트레이딩 모드 전환"""
    try:
        # 실제로는 사용자 설정을 데이터베이스에 저장
        logger.info(f"User {user_id} switched to {'demo' if demo_mode else 'live'} mode")
        return True
    except Exception as e:
        logger.error(f"Failed to switch trading mode: {e}")
        return False

if __name__ == "__main__":
    import asyncio
    
    async def test_demo_trading():
        """데모 트레이딩 테스트"""
        simulator = DemoTradingSimulator()
        user_id = "test_user"
        
        # 사용자 잔고 초기화
        simulator.initialize_user_balance(user_id, 10000)
        
        # 잔고 확인
        balance = simulator.get_balance(user_id)
        print(f"Initial balance: {balance}")
        
        # 시장가 매수 주문
        order_result = await simulator.place_order(
            user_id=user_id,
            exchange="demo_exchange",
            symbol="BTC/USDT",
            side="buy",
            order_type="market",
            amount=0.01,
            current_market_price=50000
        )
        print(f"Buy order result: {order_result}")
        
        # 포지션 확인
        positions = simulator.get_positions(user_id)
        print(f"Positions: {positions}")
        
        # 시장 가격 업데이트
        simulator.update_market_prices({"BTC/USDT": 51000})
        
        # 업데이트된 포지션 확인
        positions = simulator.get_positions(user_id)
        print(f"Updated positions: {positions}")
        
        # 성과 요약
        performance = simulator.get_performance_summary(user_id)
        print(f"Performance: {performance}")
    
    asyncio.run(test_demo_trading())