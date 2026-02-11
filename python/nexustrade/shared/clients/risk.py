"""
Risk management service client.
"""
import logging
from typing import Optional, Dict, Any
from decimal import Decimal

from shared.clients.base import ServiceClient

logger = logging.getLogger(__name__)


class RiskClient(ServiceClient):
    """
    Client for risk management service.
    """

    def __init__(self, base_url: str = "http://risk:8000"):
        super().__init__(base_url, "risk")

    async def check_order_risk(
        self,
        user_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Check if an order passes risk checks.

        BUG G1: No lock - race condition allows over-exposure
        BUG G4: Timeout causes unfair rejection
        """
        response = await self.post(
            "/risk/check-order",
            json={
                "user_id": user_id,
                "symbol": symbol,
                "side": side,
                "quantity": float(quantity),
                "price": float(price) if price else None,
            },
            headers=headers,
        )

        
        if response.status_code == 200:
            return response.json()

        return {
            "approved": False,
            "reason": "risk_check_failed",
            "details": response.text,
        }

    async def get_exposure(
        self,
        user_id: str,
        symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get user's current exposure.

        BUG G2: Exposure data might be stale due to cache
        """
        params = {}
        if symbol:
            params["symbol"] = symbol

        response = await self.get(
            f"/risk/exposure/{user_id}",
            params=params,
            coalesce=True,  
        )

        if response.status_code == 200:
            return response.json()
        return {"total_exposure": 0, "positions": []}

    async def get_margin_status(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Get user's margin status.

        BUG G3: Threshold comparison is off-by-one
        """
        response = await self.get(f"/risk/margin/{user_id}")

        if response.status_code == 200:
            data = response.json()
            
            return data

        return {
            "equity": Decimal("0"),
            "margin_used": Decimal("0"),
            "margin_available": Decimal("0"),
            "margin_ratio": 0.0,
        }

    async def check_multi_leg_order(
        self,
        user_id: str,
        legs: list,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Check risk for multi-leg order (spread, straddle, etc).

        BUG G5: Legs not checked atomically - partial approval possible
        """
        results = []

        
        for leg in legs:
            result = await self.check_order_risk(
                user_id=user_id,
                symbol=leg["symbol"],
                side=leg["side"],
                quantity=Decimal(str(leg["quantity"])),
                price=Decimal(str(leg["price"])) if leg.get("price") else None,
                headers=headers,
            )
            results.append(result)

        # If any leg fails, the whole order should fail
        
        
        #   - shared/clients/risk.py: Implement two-phase check (reserve -> confirm/rollback)
        #   - services/risk/views.py: Add reserve_margin() and release_margin() endpoints
        #   - services/orders/views.py: Call release_margin() if any leg fails validation
        # Fixing only this file (e.g., checking all legs before approving) doesn't prevent
        # margin from being reserved during the check_order_risk calls above.
        all_approved = all(r["approved"] for r in results)

        return {
            "approved": all_approved,
            "leg_results": results,
        }

    async def calculate_var(
        self,
        user_id: str,
        confidence_level: float = 0.99,
        time_horizon: int = 1,
    ) -> Dict[str, Any]:
        """
        Calculate Value at Risk for user's portfolio.

        BUG G6: Large positions cause overflow in calculation
        """
        response = await self.get(
            f"/risk/var/{user_id}",
            params={
                "confidence": confidence_level,
                "horizon": time_horizon,
            },
        )

        if response.status_code == 200:
            data = response.json()
            
            if data.get("var") == "NaN":
                logger.warning(f"VaR calculation returned NaN for user {user_id}")
            return data

        return {"var": 0, "error": response.text}
