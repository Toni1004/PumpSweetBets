import time
from solders.keypair import Keypair
from config import (
    SOL_WATCH_ADDRESS,
    SOL_WATCH_PRIVATE_KEY,
    POLYMARKET_SOL_DEPOSIT,
    SOL_THRESHOLD,
    SOL_SEND_PERCENT,
    SOL_POLL_INTERVAL,
    USDC_POLL_INTERVAL,
    BRIDGE_TIMEOUT,
    USDC_BRIDGE_THRESHOLD,
    USDC_BET_PERCENT,
    USDC_RETRY_THRESHOLD,
    TOKEN_ID,
    BET_SIDE
)
from solana_utils import get_sol_balance, send_sol, verify_sol_sent
from polymarket_utils import get_poly_client, get_usdc_balance, place_bet
from py_clob_client.order_builder.constants import BUY


def wait_for_bridge(client, pre_bridge_balance: float) -> bool:
    print(f"[INFO] Waiting for bridge (polling every {USDC_POLL_INTERVAL}s, max {BRIDGE_TIMEOUT}s)...")
    print(f"[INFO] Pre-bridge balance: ${pre_bridge_balance:.2f}")
    print(f"[INFO] Need increase of: ${USDC_BRIDGE_THRESHOLD:.2f}")
    
    start_time = time.time()
    
    while time.time() - start_time < BRIDGE_TIMEOUT:
        current_balance = get_usdc_balance(client)
        
        if current_balance < 0:
            print(f"[WARN] Failed to get balance, retrying...")
            time.sleep(USDC_POLL_INTERVAL)
            continue
        
        increase = current_balance - pre_bridge_balance
        print(f"[{time.strftime('%H:%M:%S')}] USDC: ${current_balance:.2f} (+${increase:.2f})")
        
        if increase >= USDC_BRIDGE_THRESHOLD:
            print(f"[SUCCESS] Bridge complete! +${increase:.2f}")
            return True
        
        time.sleep(USDC_POLL_INTERVAL)
    
    print(f"[ERROR] Bridge timeout after {BRIDGE_TIMEOUT}s")
    return False


def bet_loop(client):
    while True:
        balance = get_usdc_balance(client)
        
        if balance < 0:
            print(f"[ERROR] Can't get balance, stopping bet loop")
            break
        
        if balance < USDC_RETRY_THRESHOLD:
            print(f"[INFO] Balance ${balance:.2f} < ${USDC_RETRY_THRESHOLD}, done betting")
            break
        
        bet_amount = balance * USDC_BET_PERCENT
        print(f"\n[BET] Balance: ${balance:.2f} → Betting: ${bet_amount:.2f}")
        
        result = place_bet(client, bet_amount)
        
        if result.get("success"):
            print(f"[SUCCESS] Order matched!")
            print(f"  Status: {result.get('status')}")
            print(f"  Shares: {result.get('takingAmount')}")
            print(f"  Cost: ${float(result.get('makingAmount', 0)):.2f}")
            if result.get('transactionsHashes'):
                print(f"  TX: {result['transactionsHashes'][0]}")
        else:
            print(f"[WARN] Order may have failed: {result}")
        
        time.sleep(10)
    
    print(f"[INFO] Bet loop complete")


def run_bot():
    print("=" * 60)
    print("POLYMARKET AUTO-BET BOT")
    print("=" * 60)
    print(f"Watching: {SOL_WATCH_ADDRESS}")
    print(f"Threshold: {SOL_THRESHOLD} SOL")
    print(f"Token: {TOKEN_ID[:30]}...")
    print(f"Side: {'YES' if BET_SIDE == BUY else 'NO'}")
    print(f"SOL poll: {SOL_POLL_INTERVAL}s | USDC poll: {USDC_POLL_INTERVAL}s")
    print("=" * 60)
    
    sol_keypair = Keypair.from_base58_string(SOL_WATCH_PRIVATE_KEY)
    poly_client = get_poly_client()
    
    initial_usdc = get_usdc_balance(poly_client)
    if initial_usdc >= 0:
        print(f"[INFO] Initial Polymarket balance: ${initial_usdc:.2f}")
    else:
        print(f"[WARN] Could not fetch initial balance")
    
    print(f"\n[INFO] Starting SOL polling...\n")
    
    while True:
        try:
            sol_balance = get_sol_balance(SOL_WATCH_ADDRESS)
            
            if sol_balance < 0:
                print(f"[{time.strftime('%H:%M:%S')}] SOL balance: ERROR")
                time.sleep(SOL_POLL_INTERVAL)
                continue
            
            print(f"[{time.strftime('%H:%M:%S')}] SOL balance: {sol_balance:.4f}")
            
            if sol_balance < SOL_THRESHOLD:
                time.sleep(SOL_POLL_INTERVAL)
                continue
            
            print(f"\n{'='*60}")
            print(f"[TRIGGER] SOL balance {sol_balance:.4f} >= {SOL_THRESHOLD}")
            print(f"{'='*60}\n")
            
            pre_bridge_usdc = get_usdc_balance(poly_client)
            if pre_bridge_usdc < 0:
                print(f"[ERROR] Can't get USDC balance, aborting")
                time.sleep(SOL_POLL_INTERVAL)
                continue
            
            send_amount = sol_balance * SOL_SEND_PERCENT
            send_amount = min(send_amount, sol_balance - 0.01)
            
            print(f"[INFO] Sending {send_amount:.4f} SOL to Polymarket...")
            
            tx_sig = send_sol(sol_keypair, POLYMARKET_SOL_DEPOSIT, send_amount)
            
            if not tx_sig:
                print(f"[ERROR] SOL transfer failed, back to polling")
                time.sleep(SOL_POLL_INTERVAL)
                continue
            
            print(f"[INFO] TX submitted: {tx_sig}")
            
            if not verify_sol_sent(SOL_WATCH_ADDRESS, sol_balance, send_amount):
                print(f"[ERROR] SOL doesn't appear to have left, back to polling")
                time.sleep(SOL_POLL_INTERVAL)
                continue
            
            print(f"[INFO] SOL transfer confirmed")
            
            if not wait_for_bridge(poly_client, pre_bridge_usdc):
                print(f"[ERROR] Bridge failed/timeout, back to polling")
                time.sleep(SOL_POLL_INTERVAL)
                continue
            
            bet_loop(poly_client)
            
            print(f"\n[INFO] Cycle complete, resuming SOL polling...\n")
            
        except KeyboardInterrupt:
            print("\n[INFO] Bot stopped by user")
            break
        except Exception as e:
            print(f"[ERROR] Unexpected: {e}")
            time.sleep(SOL_POLL_INTERVAL)

