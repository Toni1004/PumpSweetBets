import time
import requests
from solana.rpc.api import Client as SolanaClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction
from solders.message import Message
from config import (
    SOLANA_PUBLIC_RPC,
    SOLANA_HELIUS_RPC,
    SOL_VERIFY_ATTEMPTS,
    SOL_VERIFY_DELAY
)


def get_sol_balance(address: str) -> float:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [address]
    }
    
    try:
        resp = requests.post(SOLANA_PUBLIC_RPC, json=payload, timeout=10)
        data = resp.json()
        if "result" in data:
            return data["result"]["value"] / 1_000_000_000
    except Exception as e:
        print(f"[WARN] Public RPC failed: {e}")
    
    try:
        resp = requests.post(SOLANA_HELIUS_RPC, json=payload, timeout=10)
        data = resp.json()
        if "result" in data:
            return data["result"]["value"] / 1_000_000_000
    except Exception as e:
        print(f"[ERROR] Helius RPC failed: {e}")
    
    return -1


def send_sol(from_keypair: Keypair, to_address: str, amount_sol: float) -> str:
    try:
        client = SolanaClient(SOLANA_PUBLIC_RPC)
        dest = Pubkey.from_string(to_address)
        lamports = int(amount_sol * 1_000_000_000)
        
        ix = transfer(TransferParams(
            from_pubkey=from_keypair.pubkey(),
            to_pubkey=dest,
            lamports=lamports
        ))
        
        blockhash = client.get_latest_blockhash().value.blockhash
        msg = Message.new_with_blockhash([ix], from_keypair.pubkey(), blockhash)
        tx = Transaction.new_unsigned(msg)
        tx.sign([from_keypair], blockhash)
        
        result = client.send_transaction(tx)
        return str(result.value)
    except Exception as e:
        print(f"[ERROR] SOL transfer failed: {e}")
        return ""


def verify_sol_sent(address: str, balance_before: float, amount_sent: float) -> bool:
    print(f"[INFO] Verifying SOL left (was {balance_before:.4f}, sent {amount_sent:.4f})...")
    
    for attempt in range(SOL_VERIFY_ATTEMPTS):
        time.sleep(SOL_VERIFY_DELAY)
        current = get_sol_balance(address)
        
        if current < 0:
            print(f"[WARN] RPC error on attempt {attempt + 1}")
            continue
        
        expected_after = balance_before - amount_sent
        print(f"[INFO] Check {attempt + 1}: balance={current:.4f}, expected~={expected_after:.4f}")
        
        if current <= balance_before - (amount_sent * 0.8):
            return True
    
    return False

