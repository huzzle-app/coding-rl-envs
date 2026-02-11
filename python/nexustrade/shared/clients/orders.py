"""
Orders service client.
"""
import logging
from typing import Optional, Dict, Any, List
from decimal import Decimal
from uuid import UUID

from shared.clients.base import ServiceClient

logger = logging.getLogger(__name__)


class OrdersClient(ServiceClient):
    """
    Client for orders service.
    """

    def __init__(self, base_url: str = "http://orders:8000"):
        super().__init__(base_url, "orders")

    async def create_order(
        self,
        user_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        time_in_force: str = "day",
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new order.

        BUG C4: Deadline not propagated - upstream service timeout ignored
        """
        response = await self.post(
            "/orders",
            json={
                "user_id": user_id,
                "symbol": symbol,
                "side": side,
                "order_type": order_type,
                
                "quantity": float(quantity),
                "price": float(price) if price else None,
                "stop_price": float(stop_price) if stop_price else None,
                "time_in_force": time_in_force,
            },
            headers=headers,
        )

        if response.status_code != 201:
            raise Exception(f"Failed to create order: {response.text}")

        return response.json()

    async def get_order(
        self,
        order_id: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get order by ID."""
        response = await self.get(
            f"/orders/{order_id}",
            headers=headers,
        )

        if response.status_code == 200:
            return response.json()
        return None

    async def cancel_order(
        self,
        order_id: str,
        reason: str = "user_requested",
        headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Cancel an order.

        BUG B2: No idempotency - duplicate cancels processed
        """
        response = await self.post(
            f"/orders/{order_id}/cancel",
            json={"reason": reason},
            headers=headers,
        )

        return response.status_code == 200

    async def list_orders(
        self,
        user_id: str,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        List orders for a user.

        BUG I1: SQL injection via order_by parameter
        """
        params = {
            "user_id": user_id,
            "limit": limit,
            "offset": offset,
        }
        if status:
            params["status"] = status
        if symbol:
            params["symbol"] = symbol
        if order_by:
            
            params["order_by"] = order_by

        response = await self.get(
            "/orders",
            params=params,
            headers=headers,
        )

        if response.status_code == 200:
            return response.json().get("orders", [])
        return []

    async def get_order_book(
        self,
        symbol: str,
        depth: int = 10,
    ) -> Dict[str, Any]:
        """Get order book for a symbol."""
        response = await self.get(
            f"/orderbook/{symbol}",
            params={"depth": depth},
            coalesce=True,  # Multiple users can share this read
        )

        if response.status_code == 200:
            return response.json()
        return {"bids": [], "asks": []}
