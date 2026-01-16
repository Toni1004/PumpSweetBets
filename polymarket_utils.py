from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, BalanceAllowanceParams, AssetType
from config import POLY_PRIVATE_KEY, POLY_FUNDER, TOKEN_ID, BET_SIDE


def get_poly_client() -> ClobClient:
    client = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        key=POLY_PRIVATE_KEY,
        signature_type=2,
        funder=POLY_FUNDER,
    )
    client.set_api_creds(client.create_or_derive_api_creds())
    return client


def get_usdc_balance(client: ClobClient) -> float:
    try:
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=2)
        resp = client.get_balance_allowance(params)
        return int(resp["balance"]) / 1_000_000
    except Exception as e:
        print(f"[ERROR] Failed to get USDC balance: {e}")
        return -1


def get_fill_price_and_size(client: ClobClient, amount_usdc: float):
    try:
        book = client.get_order_book(TOKEN_ID)
        asks_sorted = sorted(book.asks, key=lambda x: float(x.price))
        
        cumulative_cost = 0
        cumulative_shares = 0
        
        for ask in asks_sorted:
            price = float(ask.price)
            size = float(ask.size)
            level_cost = price * size
            
            if cumulative_cost + level_cost >= amount_usdc:
                remaining = amount_usdc - cumulative_cost
                shares_needed = remaining / price
                cumulative_shares += shares_needed
                return (price, cumulative_shares)
            
            cumulative_cost += level_cost
            cumulative_shares += size
        
        return (None, None)
    except Exception as e:
        print(f"[ERROR] Failed to get order book: {e}")
        return (None, None)


def place_bet(client: ClobClient, amount_usdc: float) -> dict:
    print(f"[INFO] Finding fill price for ${amount_usdc:.2f}...")
    
    fill_price, shares = get_fill_price_and_size(client, amount_usdc)
    
    if fill_price is None:
        return {"success": False, "error": "Not enough liquidity"}
    
    print(f"[INFO] Will buy {shares:.2f} shares at max {fill_price:.4f} ({fill_price*100:.1f}¢)")
    print(f"[INFO] Max cost: ${shares * fill_price:.2f}")
    
    try:
        order_args = OrderArgs(
            price=fill_price,
            size=shares,
            side=BET_SIDE,
            token_id=TOKEN_ID
        )
        signed_order = client.create_order(order_args)
        resp = client.post_order(signed_order, OrderType.GTC)
        return resp
    except Exception as e:
        print(f"[ERROR] Bet failed: {e}")
        return {"success": False, "error": str(e)}

