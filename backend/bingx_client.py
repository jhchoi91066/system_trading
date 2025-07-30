import hmac
import hashlib
import requests
import time
import urllib.parse
from typing import Dict, Any, Optional, List

class BingXClient:
    BASE_URL = "https://open-api-vst.bingx.com" # VST (Virtual USDT) API Endpoint

    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def _sign(self, method: str, path: str, params: Dict[str, Any]) -> str:
        # BingX HMAC SHA256 authentication
        # All parameters (including query and body) must be sorted alphabetically
        # and then concatenated into a query string.
        
        # Add timestamp and API key
        params["timestamp"] = str(int(time.time() * 1000))
        params["apiKey"] = self.api_key

        # Sort parameters alphabetically by key
        sorted_params = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_params)

        # Create signature
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature

    def _send_request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if params is None:
            params = {}
        
        # Combine params and body for signing
        all_params = {**params, **(body if body else {})}
        signature = self._sign(method, path, all_params)
        
        headers = {
            "X-BX-APIKEY": self.api_key,
            "X-BX-SIGN": signature,
            "X-BX-TIMESTAMP": str(int(time.time() * 1000)),
            "Content-Type": "application/json" if body else "application/x-www-form-urlencoded"
        }

        url = f"{self.BASE_URL}{path}"
        
        if method == "GET":
            response = requests.get(url, params=all_params, headers=headers)
        elif method == "POST":
            response = requests.post(url, json=body if body else all_params, headers=headers) # BingX often uses JSON body for POST
        # Add other methods (PUT, DELETE) if needed
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status() # Raise an exception for HTTP errors
        return response.json()

    # Public API Endpoints (Examples)
    def get_server_time(self) -> Dict[str, Any]:
        path = "/api/v1/server/time"
        return self._send_request("GET", path)

    def get_market_depth(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        path = "/api/v1/market/depth"
        params = {"symbol": symbol, "limit": limit}
        return self._send_request("GET", path, params=params)

    # Account Endpoints (Examples)
    def get_balance(self, currency: Optional[str] = None) -> Dict[str, Any]:
        path = "/api/v1/user/balance"
        params = {}
        if currency:
            params["currency"] = currency
        return self._send_request("GET", path, params=params)

    # Trading Endpoints (Examples)
    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, price: Optional[float] = None) -> Dict[str, Any]:
        path = "/api/v1/user/trade" # Example path, verify with BingX API docs
        body = {
            "symbol": symbol,
            "side": side.upper(), # BUY/SELL
            "type": order_type.upper(), # LIMIT/MARKET
            "quantity": quantity,
        }
        if price:
            body["price"] = price
        return self._send_request("POST", path, body=body)

    def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        path = "/api/v1/user/cancelOrder" # Example path
        body = {
            "symbol": symbol,
            "orderId": order_id
        }
        return self._send_request("POST", path, body=body)

    def get_open_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        path = "/api/v1/user/openOrders" # Example path
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._send_request("GET", path, params=params)

    def get_order_history(self, symbol: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        path = "/api/v1/user/historyOrders" # Example path
        params = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        return self._send_request("GET", path, params=params)

# Example Usage (for testing purposes)
if __name__ == "__main__":
    # Replace with your actual BingX VST API Key and Secret
    # For VST, you need to generate a separate API key from the BingX website
    # usually under "API Management" -> "Virtual Account API" or similar.
    API_KEY = "YOUR_BINGX_VST_API_KEY"
    SECRET_KEY = "YOUR_BINGX_VST_SECRET_KEY"

    client = BingXClient(API_KEY, SECRET_KEY)

    try:
        # Get server time
        server_time = client.get_server_time()
        print(f"Server Time: {server_time}")

        # Get VST balance (example for USDT)
        balance = client.get_balance(currency="USDT")
        print(f"VST USDT Balance: {balance}")

        # Place a VST test order (example: BTC/USDT, buy 0.001 BTC at market price)
        # IMPORTANT: Verify symbol and quantity limits for VST trading
        # order_result = client.place_order(symbol="BTC-USDT", side="BUY", order_type="MARKET", quantity=0.001)
        # print(f"Place Order Result: {order_result}")

        # Get open orders
        open_orders = client.get_open_orders(symbol="BTC-USDT")
        print(f"Open Orders: {open_orders}")

        # Get order history
        order_history = client.get_order_history(symbol="BTC-USDT")
        print(f"Order History: {order_history}")

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"An error occurred: {e}")
