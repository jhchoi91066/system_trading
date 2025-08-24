"""
포지션 관리 시스템
- 현재 열린 포지션 추적
- 손절/익절 자동 실행
- 다중 포지션 관리
- 포지션별 리스크 계산
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import json
from persistent_storage import persistent_storage

logger = logging.getLogger(__name__)

@dataclass
class Position:
    """포지션 정보"""
    user_id: str
    exchange_name: str
    symbol: str
    strategy_id: int
    position_id: str
    side: str  # 'long' or 'short'
    entry_price: float
    quantity: float
    entry_time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    status: str = "open"  # open, closed, partial
    metadata: Dict = field(default_factory=dict)

class PositionManager:
    def __init__(self):
        self.positions: Dict[str, Position] = {}  # position_id -> Position
        self.user_positions: Dict[str, List[str]] = {}  # user_id -> [position_ids]
        self.symbol_positions: Dict[str, List[str]] = {}  # symbol -> [position_ids]
        
    def create_position(self, user_id: str, exchange_name: str, symbol: str, 
                       strategy_id: int, side: str, entry_price: float, 
                       quantity: float, stop_loss_pct: float = 5.0, 
                       take_profit_pct: float = 10.0) -> Position:
        """새 포지션 생성"""
        try:
            position_id = f"{user_id}_{exchange_name}_{symbol}_{strategy_id}_{int(datetime.now().timestamp())}"
            
            # entry_price가 None인 경우 처리
            if entry_price is None:
                logger.error(f"entry_price is None for position creation: {symbol}")
                return None
            
            # 손절/익절 가격 계산
            if side == 'long':
                stop_loss = entry_price * (1 - stop_loss_pct / 100) if stop_loss_pct > 0 else None
                take_profit = entry_price * (1 + take_profit_pct / 100) if take_profit_pct > 0 else None
            else:  # short
                stop_loss = entry_price * (1 + stop_loss_pct / 100) if stop_loss_pct > 0 else None
                take_profit = entry_price * (1 - take_profit_pct / 100) if take_profit_pct > 0 else None
            
            position = Position(
                user_id=user_id,
                exchange_name=exchange_name,
                symbol=symbol,
                strategy_id=strategy_id,
                position_id=position_id,
                side=side,
                entry_price=entry_price,
                quantity=quantity,
                entry_time=datetime.now(),
                stop_loss=stop_loss,
                take_profit=take_profit,
                current_price=entry_price
            )
            
            # 포지션 저장
            self.positions[position_id] = position
            
            # 인덱스 업데이트
            if user_id not in self.user_positions:
                self.user_positions[user_id] = []
            self.user_positions[user_id].append(position_id)
            
            if symbol not in self.symbol_positions:
                self.symbol_positions[symbol] = []
            self.symbol_positions[symbol].append(position_id)
            
            logger.info(f"Created new {side} position for {symbol}: {position_id}")
            return position
            
        except Exception as e:
            logger.error(f"Error creating position: {e}")
            raise
    
    def get_position(self, position_id: str) -> Optional[Position]:
        """포지션 조회"""
        return self.positions.get(position_id)
    
    def get_user_positions(self, user_id: str, status: str = None) -> List[Position]:
        """특정 사용자의 포지션 조회"""
        user_position_ids = self.user_positions.get(user_id, [])
        positions = [self.positions[pid] for pid in user_position_ids if pid in self.positions]
        
        if status:
            positions = [p for p in positions if p.status == status]
            
        return positions
    
    def get_symbol_positions(self, user_id: str, symbol: str, status: str = None) -> List[Position]:
        """특정 심볼의 포지션 조회"""
        user_positions = self.get_user_positions(user_id, status)
        return [p for p in user_positions if p.symbol == symbol]
    
    def update_position_price(self, position_id: str, current_price: float):
        """포지션 현재가 및 손익 업데이트"""
        position = self.positions.get(position_id)
        if not position:
            return
            
        position.current_price = current_price
        
        # 미실현 손익 계산
        if position.side == 'long':
            position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
        else:  # short
            position.unrealized_pnl = (position.entry_price - current_price) * position.quantity
    
    def check_stop_loss_take_profit(self, position_id: str) -> Optional[str]:
        """손절/익절 조건 확인"""
        position = self.positions.get(position_id)
        if not position or position.status != "open":
            return None
            
        current_price = position.current_price
        
        # 손절 확인
        if position.stop_loss:
            if position.side == 'long' and current_price <= position.stop_loss:
                return "stop_loss"
            elif position.side == 'short' and current_price >= position.stop_loss:
                return "stop_loss"
        
        # 익절 확인  
        if position.take_profit:
            if position.side == 'long' and current_price >= position.take_profit:
                return "take_profit"
            elif position.side == 'short' and current_price <= position.take_profit:
                return "take_profit"
        
        return None
    
    def close_position(self, position_id: str, close_price: float, close_reason: str = "manual") -> bool:
        """포지션 청산"""
        try:
            position = self.positions.get(position_id)
            if not position:
                logger.warning(f"Position {position_id} not found")
                return False
            
            # 실현 손익 계산
            if position.side == 'long':
                position.realized_pnl = (close_price - position.entry_price) * position.quantity
            else:  # short
                position.realized_pnl = (position.entry_price - close_price) * position.quantity
            
            position.status = "closed"
            position.current_price = close_price
            position.metadata['close_reason'] = close_reason
            position.metadata['close_time'] = datetime.now().isoformat()
            
            logger.info(f"Closed position {position_id}: PnL = {position.realized_pnl:.4f}, Reason = {close_reason}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing position {position_id}: {e}")
            return False
    
    def get_total_exposure(self, user_id: str, symbol: str = None) -> float:
        """총 노출 금액 계산"""
        positions = self.get_user_positions(user_id, status="open")
        
        if symbol:
            positions = [p for p in positions if p.symbol == symbol]
        
        total_exposure = sum(p.entry_price * p.quantity for p in positions)
        return total_exposure
    
    def get_portfolio_pnl(self, user_id: str) -> Dict:
        """포트폴리오 손익 통계"""
        positions = self.get_user_positions(user_id)
        
        open_positions = [p for p in positions if p.status == "open"]
        closed_positions = [p for p in positions if p.status == "closed"]
        
        total_unrealized = sum(p.unrealized_pnl for p in open_positions)
        total_realized = sum(p.realized_pnl for p in closed_positions)
        
        winning_trades = len([p for p in closed_positions if p.realized_pnl > 0])
        losing_trades = len([p for p in closed_positions if p.realized_pnl < 0])
        total_trades = len(closed_positions)
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            "total_unrealized_pnl": total_unrealized,
            "total_realized_pnl": total_realized,
            "total_pnl": total_unrealized + total_realized,
            "open_positions": len(open_positions),
            "closed_positions": len(closed_positions),
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate
        }
    
    def cleanup_old_positions(self, days: int = 30):
        """오래된 청산 포지션 정리"""
        cutoff_date = datetime.now() - timedelta(days=days)
        positions_to_remove = []
        
        for position_id, position in self.positions.items():
            if (position.status == "closed" and 
                position.entry_time < cutoff_date):
                positions_to_remove.append(position_id)
        
        for position_id in positions_to_remove:
            self._remove_position(position_id)
        
        logger.info(f"Cleaned up {len(positions_to_remove)} old positions")
    
    def _remove_position(self, position_id: str):
        """포지션 제거 (내부 메서드)"""
        position = self.positions.get(position_id)
        if not position:
            return
            
        # 인덱스에서 제거
        user_id = position.user_id
        symbol = position.symbol
        
        if user_id in self.user_positions:
            if position_id in self.user_positions[user_id]:
                self.user_positions[user_id].remove(position_id)
        
        if symbol in self.symbol_positions:
            if position_id in self.symbol_positions[symbol]:
                self.symbol_positions[symbol].remove(position_id)
        
        # 메인 딕셔너리에서 제거
        del self.positions[position_id]
    
    def save_position_to_storage(self, position: Position):
        """포지션을 영구 저장소에 저장"""
        try:
            position_data = {
                "user_id": position.user_id,
                "exchange_name": position.exchange_name,
                "symbol": position.symbol,
                "strategy_id": position.strategy_id,
                "position_id": position.position_id,
                "side": position.side,
                "entry_price": position.entry_price,
                "quantity": position.quantity,
                "entry_time": position.entry_time.isoformat(),
                "stop_loss": position.stop_loss,
                "take_profit": position.take_profit,
                "current_price": position.current_price,
                "unrealized_pnl": position.unrealized_pnl,
                "realized_pnl": position.realized_pnl,
                "status": position.status,
                "metadata": position.metadata
            }
            
            # 영구 저장소에 저장 (추후 구현)
            logger.info(f"Position {position.position_id} saved to storage")
            
        except Exception as e:
            logger.error(f"Error saving position to storage: {e}")

# 글로벌 인스턴스
position_manager = PositionManager()