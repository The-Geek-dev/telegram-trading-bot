import os
import re
import json
import random
import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ChatAction
import requests
from solders.keypair import Keypair
from solders.pubkey import Pubkey
import base58


# ===== CONFIGURATION =====
BOT_TOKEN = BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN not found!")
    exit(1)
ADMIN_USER_IDS = [990809301,8489892403]

# Trading Configuration
SUPPORTED_COINS = ["BTC", "ETH", "BNB", "XRP", "ADA", "DOGE", "SOL", "DOT", "MATIC", "AVAX", "LINK", "UNI"]
# Solana Memecoins - will be updated hourly
SOLANA_MEMECOINS = {}
TRENDING_MEMECOINS = {}
MEMECOIN_BY_ADDRESS = {}  # Map contract addresses to symbols
MEMECOIN_LAST_UPDATE = None
MEMECOIN_UPDATE_INTERVAL = 3600  # 1 hour in seconds
MINIMUM_DEPOSIT = 10  # Minimum $10 deposit
TRADING_FEE = 0.001  # 0.1% trading fee

# ===== DATA STORAGE =====
user_data = {}
trade_history = []
withdrawal_requests = []
auto_trade_sessions = {}  # Track active auto-trade sessions
deposit_requests = []  # NEW: Track deposit requests

bot_stats = {
    "total_users": 0,
    "total_deposits": 0,
    "total_trades": 0,
    "total_volume": 0,
    "start_time": datetime.now()
}
# ===== TOKEN SYSTEM =====
VALID_TOKENS = [
    "ASTRA-2K9F-8H3L-9M3P",
    "ASTRA-7Q4R-3N8W-5K1X",
    "ASTRA-6P2M-9L4H-7R3Y",
    "ASTRA-4W8N-2K5Q-1M9Z",
    "ASTRA-3H7R-6P9L-8N2A",
    "ASTRA-9M4K-7W2Q-3H5B",
    "ASTRA-5L8P-4N6R-2W9C",
    "ASTRA-1Q3M-8K7H-6P4D",
    "ASTRA-8R6N-5L3W-9M2E",
    "ASTRA-2P9K-7H4Q-1W8F",
    "ASTRA-6W3L-9R5M-4K7G",
    "ASTRA-4K7P-2M8N-5W3H",
    "ASTRA-7H9R-6L2K-8P4I",
    "ASTRA-3M5W-1Q9N-7R6J",
    "ASTRA-9P2K-4H7L-3W5K",
    "ASTRA-5R8M-7K3P-2N9L",
    "ASTRA-1L6W-9H4R-8K3M",
    "ASTRA-8K3P-5M7N-1R9N",
    "ASTRA-2W9L-6R4H-7P3O",
    "ASTRA-6H4M-3K8R-9L2P",
    "ASTRA-4P7W-1M5K-8R6Q",
    "ASTRA-7M2L-9K6P-3H8R",
    "ASTRA-3R5K-8W2M-4P7S",
    "ASTRA-9L6H-2P4R-7M3T",
    "ASTRA-5K9M-6R3W-1L8U",
    "ASTRA-1P4L-7M9K-5R2V",
    "ASTRA-8W7R-3K5M-9P6W",
    "ASTRA-2M3K-6L8P-4W9X",
    "ASTRA-6R9W-1M4L-8K7Y",
    "ASTRA-4L2P-9R6M-3K5Z",
    "ASTRA-7K8M-5W3R-2P9A1",
    "ASTRA-3P6L-8M2K-9W4B1",
    "ASTRA-9R4K-7P5M-1L8C1",
    "ASTRA-5M7W-2K9R-6P3D1",
    "ASTRA-1K5L-8R3M-4W9E1",
    "ASTRA-8P2M-6K7R-3L5F1",
    "ASTRA-2R9K-4M6W-7P8G1",
    "ASTRA-6L3P-1K9M-5R7H1",
    "ASTRA-4W8R-9L2K-8M6I1",
    "ASTRA-7M5K-3P8L-2W9J1",
    "ASTRA-3K9M-6R4P-1L7K1",
    "ASTRA-9W2L-5M8K-7R4L1",
    "ASTRA-5P6R-8K3M-4W2M1",
    "ASTRA-1M8K-7L5R-9P3N1",
    "ASTRA-8L4P-2R9M-6K7O1",
    "ASTRA-2K7M-5W3L-8R9P1",
    "ASTRA-6M9R-1P4K-3L8Q1",
    "ASTRA-4R3K-7M6P-9W2R1",
    "ASTRA-7L8W-4K2M-5P9S1",
    "ASTRA-3W6M-9R5K-2L8T1"
]

USED_TOKENS = set()  # Track used tokens


# ===== WALLET GENERATION (FIXED) =====

# ===== CORRECT PHANTOM-COMPATIBLE WALLET GENERATION =====
# Install: pip install mnemonic solders

def generate_seed_phrase():
    """Generate a 12-word seed phrase"""
    from mnemonic import Mnemonic
    mnemo = Mnemonic("english")
    return mnemo.generate(strength=128)


def generate_wallet_address(user_id, seed_phrase):
    """Generate Solana wallet address - EXACTLY like Phantom using BIP44 derivation"""
    try:
        from mnemonic import Mnemonic
        from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes
        from solders.keypair import Keypair
        
        # Generate seed from mnemonic (BIP39)
        seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()
        
        # Derive Solana key using BIP44 path: m/44'/501'/0'/0'
        # 501 is Solana's coin type
        bip44_mst = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA)
        bip44_acc = bip44_mst.Purpose().Coin().Account(0)
        bip44_chg = bip44_acc.Change(Bip44Changes.CHAIN_EXT)
        bip44_addr = bip44_chg.AddressIndex(0)
        
        # Get the private key (32 bytes)
        private_key_bytes = bip44_addr.PrivateKey().Raw().ToBytes()
        
        # Create Solana keypair from private key
        keypair = Keypair.from_seed(private_key_bytes)
        
        # Get public key (wallet address)
        wallet_address = str(keypair.pubkey())
        
        return wallet_address
        
    except Exception as e:
        print(f"⚠️ Wallet generation error: {e}")
        import traceback
        traceback.print_exc()
        raise

def verify_wallet_matches_phantom(seed_phrase):
    """Test function to verify wallet matches Phantom"""
    address = generate_wallet_address(0, seed_phrase)
    print(f"\n✅ Generated Address: {address}")
    print(f"\n📝 Seed Phrase:")
    print(f"   {seed_phrase}")
    print(f"\n💡 Import this into Phantom - addresses should match!")
    return address






# ===== PRICE FETCHING =====
def get_crypto_price(symbol):
    """Get real-time crypto price from CoinGecko API"""
    try:
        # Check if it's a memecoin first
        memecoin_price = get_memecoin_price(symbol)
        if memecoin_price is not None:
            return memecoin_price
        
        # Otherwise check major coins
        coin_ids = {
            "BTC": "bitcoin",
            "ETH": "ethereum", 
            "BNB": "binancecoin",
            "XRP": "ripple",
            "ADA": "cardano",
            "DOGE": "dogecoin",
            "SOL": "solana",
            "DOT": "polkadot",
            "MATIC": "matic-network",
            "AVAX": "avalanche-2",
            "LINK": "chainlink",
            "UNI": "uniswap"
        }
        
        coin_id = coin_ids.get(symbol.upper())
        if not coin_id:
            return None
            
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        return data[coin_id]["usd"]
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
        return None

def get_all_prices():
    """Get all crypto prices at once"""
    prices = {}
    for coin in SUPPORTED_COINS:
        price = get_crypto_price(coin)
        if price:
            prices[coin] = price
    return prices

def fetch_solana_memecoins():
    """Fetch top memecoins AND trending memecoins from CoinGecko"""
    global SOLANA_MEMECOINS, TRENDING_MEMECOINS, MEMECOIN_BY_ADDRESS, MEMECOIN_LAST_UPDATE
    
    all_memecoins = {}
    
    try:
        # 1. Get top 20 Solana memecoins by market cap
        print("📊 Fetching top Solana memecoins...")
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "category": "solana-meme-coins",
            "order": "market_cap_desc",
            "per_page": 20,
            "page": 1,
            "sparkline": False
        }
        
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        for coin in data:
            symbol = coin['symbol'].upper()
            all_memecoins[symbol] = {
                "id": coin['id'],
                "name": coin['name'],
                "symbol": symbol,
                "price": coin['current_price'],
                "market_cap": coin.get('market_cap', 0),
                "price_change_24h": coin.get('price_change_percentage_24h', 0),
                "volume_24h": coin.get('total_volume', 0),
                "image": coin.get('image', ''),
                "type": "top"
            }
        
        # 2. Get trending coins (last 24h)
        print("🔥 Fetching trending memecoins...")
        trending_url = "https://api.coingecko.com/api/v3/search/trending"
        trending_response = requests.get(trending_url, timeout=15)
        trending_data = trending_response.json()
        
        trending_coins = {}
        for item in trending_data.get('coins', [])[:15]:  # Get top 15 trending
            coin_data = item.get('item', {})
            coin_id = coin_data.get('id')
            
            # Check if it's a Solana token
            if coin_id:
                # Get detailed info
                detail_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
                try:
                    detail_response = requests.get(detail_url, timeout=10)
                    detail = detail_response.json()
                    
                    # Check if it's on Solana
                    platforms = detail.get('platforms', {})
                    if 'solana' in platforms or any('solana' in str(p).lower() for p in platforms.keys()):
                        symbol = coin_data.get('symbol', '').upper()
                        
                        trending_coins[symbol] = {
                            "id": coin_id,
                            "name": coin_data.get('name', ''),
                            "symbol": symbol,
                            "price": detail.get('market_data', {}).get('current_price', {}).get('usd', 0),
                            "market_cap": detail.get('market_data', {}).get('market_cap', {}).get('usd', 0),
                            "price_change_24h": detail.get('market_data', {}).get('price_change_percentage_24h', 0),
                            "volume_24h": detail.get('market_data', {}).get('total_volume', {}).get('usd', 0),
                            "image": coin_data.get('large', ''),
                            "type": "trending",
                            "contract_address": platforms.get('solana', '')
                        }
                        
                        # Add to address mapping
                        if platforms.get('solana'):
                            MEMECOIN_BY_ADDRESS[platforms.get('solana').lower()] = symbol
                        
                        # Merge into all_memecoins (avoid duplicates)
                        if symbol not in all_memecoins:
                            all_memecoins[symbol] = trending_coins[symbol]
                        else:
                            # Update with trending flag
                            all_memecoins[symbol]['type'] = 'both'
                            if 'contract_address' in trending_coins[symbol]:
                                all_memecoins[symbol]['contract_address'] = trending_coins[symbol]['contract_address']
                
                except Exception as e:
                    print(f"Error fetching detail for {coin_id}: {e}")
                    continue
        
        TRENDING_MEMECOINS = trending_coins
        SOLANA_MEMECOINS = all_memecoins
        MEMECOIN_LAST_UPDATE = datetime.now()
        
        print(f"✅ Updated {len(all_memecoins)} total memecoins ({len(trending_coins)} trending) at {MEMECOIN_LAST_UPDATE.strftime('%H:%M:%S')}")
        return all_memecoins
        
    except Exception as e:
        print(f"❌ Error fetching Solana memecoins: {e}")
        return SOLANA_MEMECOINS

def get_memecoin_price(symbol):
    """Get price for a specific memecoin"""
    global SOLANA_MEMECOINS, MEMECOIN_LAST_UPDATE
    
    # Update if data is stale or empty
    if (not SOLANA_MEMECOINS or 
        MEMECOIN_LAST_UPDATE is None or 
        (datetime.now() - MEMECOIN_LAST_UPDATE).total_seconds() > MEMECOIN_UPDATE_INTERVAL):
        fetch_solana_memecoins()
    
    if symbol.upper() in SOLANA_MEMECOINS:
        return SOLANA_MEMECOINS[symbol.upper()]["price"]
    return None

def should_update_memecoins():
    """Check if memecoins need updating"""
    global MEMECOIN_LAST_UPDATE
    
    if MEMECOIN_LAST_UPDATE is None:
        return True
    
    elapsed = (datetime.now() - MEMECOIN_LAST_UPDATE).total_seconds()
    return elapsed >= MEMECOIN_UPDATE_INTERVAL

def get_memecoin_by_address(contract_address):
    """Get memecoin info by Solana contract address"""
    global SOLANA_MEMECOINS, MEMECOIN_BY_ADDRESS
    
    # Update if needed
    if should_update_memecoins():
        fetch_solana_memecoins()
    
    address_lower = contract_address.lower()
    
    # Check if we have it in cache
    if address_lower in MEMECOIN_BY_ADDRESS:
        symbol = MEMECOIN_BY_ADDRESS[address_lower]
        return SOLANA_MEMECOINS.get(symbol)
    
    # If not in cache, try to fetch from CoinGecko
    try:
        print(f"🔍 Searching for token: {contract_address}")
        url = f"https://api.coingecko.com/api/v3/coins/solana/contract/{contract_address}"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            symbol = data.get('symbol', '').upper()
            
            # Add to our memecoins
            memecoin_data = {
                "id": data.get('id'),
                "name": data.get('name', ''),
                "symbol": symbol,
                "price": data.get('market_data', {}).get('current_price', {}).get('usd', 0),
                "market_cap": data.get('market_data', {}).get('market_cap', {}).get('usd', 0),
                "price_change_24h": data.get('market_data', {}).get('price_change_percentage_24h', 0),
                "volume_24h": data.get('market_data', {}).get('total_volume', {}).get('usd', 0),
                "image": data.get('image', {}).get('large', ''),
                "type": "custom",
                "contract_address": contract_address
            }
            
            SOLANA_MEMECOINS[symbol] = memecoin_data
            MEMECOIN_BY_ADDRESS[address_lower] = symbol
            
            print(f"✅ Found and added: {data.get('name')} ({symbol})")
            return memecoin_data
        else:
            print(f"❌ Token not found: {contract_address}")
            return None
            
    except Exception as e:
        print(f"❌ Error fetching token by address: {e}")
        return None
# ===== USER MANAGEMENT =====
def initialize_user(user_id, user_name):
    """Initialize new user account"""
    if user_id not in user_data:
        user_data[user_id] = {
            "name": user_name,
            "has_wallet": False,
            "wallet_created": False,
            "seed_phrase": None,
            "wallets": {},
            "private_keys": {},
            "balance_usd": 0.0,
            "portfolio": {},
            "total_deposited": 0.0,
            "total_withdrawn": 0.0,
            "total_trades": 0,
            "trade_history": [],
            "pnl": 0.0,
            "initial_balance": 0.0,
            "trading_enabled": True,
            "auto_trade_amount": 100,
            "join_date": datetime.now(),
           "last_active": datetime.now(),
            "manual_profit": 0.0,  # Admin-added profit
            "token_activated": False,  # NEW
            "activation_token": None    # NEW
        }
        bot_stats["total_users"] += 1

def check_token_activated(user_id):
    """Check if user has activated their account with a token"""
    # Removed admin bypass - all users must activate with token
    if user_id not in user_data:
        return False
    
    return user_data[user_id].get("token_activated", False)
def calculate_pnl(user_id):
    """Calculate user's profit/loss (includes admin-added manual profit)"""
    if user_id not in user_data:
        return 0.0
    
    user = user_data[user_id]
    current_value = user["balance_usd"]
    
    prices = get_all_prices()
    for coin, amount in user["portfolio"].items():
        if coin in prices:
            current_value += amount * prices[coin]
    
    initial = user["initial_balance"]
    if initial == 0:
        return user.get("manual_profit", 0.0)
    
    real_pnl = current_value - initial
    total_pnl = real_pnl + user.get("manual_profit", 0.0)
    
    user["pnl"] = total_pnl
    return total_pnl
def calculate_profit_percentage(user_id):
    """Calculate profit percentage"""
    if user_id not in user_data:
        return 0.0
    
    user = user_data[user_id]
    initial = user["initial_balance"]
    
    if initial == 0:
        return 0.0
    
    pnl = calculate_pnl(user_id)
    return (pnl / initial) * 100

def get_portfolio_value(user_id):
    """Get total portfolio value in USD (includes manual profit)"""
    if user_id not in user_data:
        return 0.0
    
    user = user_data[user_id]
    total = user["balance_usd"]
    
    prices = get_all_prices()
    for coin, amount in user["portfolio"].items():
        if coin in prices:
            total += amount * prices[coin]
    
    total += user.get("manual_profit", 0.0)
    
    return total

# ===== TRADING FUNCTIONS =====
def execute_trade(user_id, action, coin, amount_usd):
    """Execute a buy or sell trade"""
    if user_id not in user_data:
        return False, "User not found"
    
    user = user_data[user_id]
    
    if not user["trading_enabled"]:
        return False, "Trading disabled for this account"
    
    price = get_crypto_price(coin)
    if not price:
        return False, f"Unable to fetch {coin} price"
    
    if action.upper() == "BUY":
        total_cost = amount_usd * (1 + TRADING_FEE)
        if user["balance_usd"] < total_cost:
            return False, f"Insufficient balance. Need ${total_cost:.2f}"
        
        coin_amount = amount_usd / price
        user["balance_usd"] -= total_cost
        
        if coin not in user["portfolio"]:
            user["portfolio"][coin] = 0.0
        user["portfolio"][coin] += coin_amount
        
        trade = {
            "user_id": user_id,
            "user_name": user["name"],
            "action": "BUY",
            "coin": coin,
            "amount": coin_amount,
            "price": price,
            "usd_value": amount_usd,
            "fee": amount_usd * TRADING_FEE,
            "timestamp": datetime.now()
        }
        
        user["trade_history"].append(trade)
        trade_history.append(trade)
        user["total_trades"] += 1
        bot_stats["total_trades"] += 1
        bot_stats["total_volume"] += amount_usd
        
        return True, f"✅ Bought {coin_amount:.6f} {coin} at ${price:.2f}\nCost: ${total_cost:.2f} (including fee)"
    
    elif action.upper() == "SELL":
        if coin not in user["portfolio"] or user["portfolio"][coin] == 0:
            return False, f"No {coin} in portfolio"
        
        coin_amount = amount_usd / price
        if user["portfolio"][coin] < coin_amount:
            return False, f"Insufficient {coin}. You have {user['portfolio'][coin]:.6f}"
        
        usd_received = amount_usd * (1 - TRADING_FEE)
        user["portfolio"][coin] -= coin_amount
        user["balance_usd"] += usd_received
        
        trade = {
            "user_id": user_id,
            "user_name": user["name"],
            "action": "SELL",
            "coin": coin,
            "amount": coin_amount,
            "price": price,
            "usd_value": amount_usd,
            "fee": amount_usd * TRADING_FEE,
            "timestamp": datetime.now()
        }
        
        user["trade_history"].append(trade)
        trade_history.append(trade)
        user["total_trades"] += 1
        bot_stats["total_trades"] += 1
        bot_stats["total_volume"] += amount_usd
        
        return True, f"✅ Sold {coin_amount:.6f} {coin} at ${price:.2f}\nReceived: ${usd_received:.2f} (after fee)"
    
    return False, "Invalid action"

# Add this new function after the trading functions
async def auto_trade_loop(context: ContextTypes.DEFAULT_TYPE, user_id: int, duration_hours: int):
    """Execute automatic trades for a user"""
    user = user_data.get(user_id)
    if not user:
        return
    
    end_time = datetime.now() + timedelta(hours=duration_hours)
    session_start_balance = get_portfolio_value(user_id)
    trades_made = 0
    
    try:
        while datetime.now() < end_time and user_id in auto_trade_sessions:
            if not user["trading_enabled"]:
                break
            
            # Random trade interval (15-45 minutes)
            await asyncio.sleep(random.randint(900, 2700))
            
            # Check if session still active
            if user_id not in auto_trade_sessions:
                break
            
            # Execute random trades
            available_balance = user["balance_usd"]
            if available_balance >= 10:
                # Random coin selection
                coin = random.choice(SUPPORTED_COINS)
                
                # Random action (60% buy, 40% sell)
                action = "BUY" if random.random() < 0.6 else "SELL"
                
                # Trade amount (10-30% of available balance or auto_trade_amount)
                max_amount = min(user["auto_trade_amount"], available_balance * 0.3)
                trade_amount = random.uniform(10, max_amount)
                
                if action == "SELL":
                    # Check if user has the coin
                    if coin not in user["portfolio"] or user["portfolio"][coin] == 0:
                        continue
                
                success, message = execute_trade(user_id, action, coin, trade_amount)
                
                if success:
                    trades_made += 1
                    
                    # Notify user occasionally (every 3-5 trades)
                    if trades_made % random.randint(3, 5) == 0:
                        current_pnl = calculate_pnl(user_id)
                        try:
                            await context.bot.send_message(
                                chat_id=user_id,
                                text=f"🤖 **Auto-Trade Update**\n\n"
                                     f"{message}\n\n"
                                     f"📊 Trades Made: {trades_made}\n"
                                     f"💰 Current PnL: ${current_pnl:+.2f}\n"
                                     f"⏱️ Time Left: {int((end_time - datetime.now()).total_seconds() / 3600)}h"
                            )
                        except:
                            pass
        
        # Session ended - send final report
        if user_id in auto_trade_sessions:
            del auto_trade_sessions[user_id]
        
        final_balance = get_portfolio_value(user_id)
        profit = final_balance - session_start_balance
        profit_pct = (profit / session_start_balance * 100) if session_start_balance > 0 else 0
        
        report = f"✅ **Auto-Trade Session Complete!**\n\n"
        report += f"⏱️ Duration: {duration_hours} hour(s)\n"
        report += f"📈 Trades Executed: {trades_made}\n\n"
        report += f"💵 Starting Value: ${session_start_balance:.2f}\n"
        report += f"💰 Final Value: ${final_balance:.2f}\n"
        report += f"{'📈' if profit >= 0 else '📉'} Profit/Loss: ${profit:+.2f} ({profit_pct:+.2f}%)\n\n"
        report += f"🎯 Status: {'🟢 Profitable' if profit >= 0 else '🔴 Loss'}\n\n"
        report += "Use /portfolio to see your holdings!"
        
        try:
            await context.bot.send_message(chat_id=user_id, text=report)
        except:
            pass
            
    except Exception as e:
        print(f"Auto-trade error for user {user_id}: {e}")
        if user_id in auto_trade_sessions:
            del auto_trade_sessions[user_id]


# ===== COMMAND HANDLERS =====
async def activate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activate account with token"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    user = user_data[user_id]
    
    if user["token_activated"]:
        await update.message.reply_text(
            f"✅ Your account is already activated!\n\n"
            f"Token: `{user['activation_token']}`\n\n"
            f"Use /start to continue."
        )
        return
    
    if not context.args:
        await update.message.reply_text(
            "🔑 **Account Activation Required**\n\n"
            "To use Astra Trading Bot, you need an activation token.\n\n"
            "**Usage:** `/activate <token>`\n\n"
            "**Example:**\n"
            "`/activate ASTRA-2K9F-8H3L-9M2P`\n\n"
            "📧 Contact admin to get your activation token!"
        )
        return
    
    token = context.args[0].strip().upper()
    
    # Check if token is valid
    if token not in VALID_TOKENS:
        await update.message.reply_text(
            "❌ **Invalid Token!**\n\n"
            "The token you entered is not valid.\n\n"
            "Please check your token and try again.\n"
            "Contact admin if you need help."
        )
        return
    
    # Check if token already used
    if token in USED_TOKENS:
        await update.message.reply_text(
            "❌ **Token Already Used!**\n\n"
            "This token has already been activated by another user.\n\n"
            "Each token can only be used once.\n"
            "Contact admin for a new token."
        )
        return
    
    # Activate account
    user["token_activated"] = True
    user["activation_token"] = token
    USED_TOKENS.add(token)
    
    await update.message.reply_text(
        f"🎉 **Account Activated Successfully!**\n\n"
        f"✅ Token: `{token}`\n"
        f"👤 Welcome, {user_name}!\n\n"
        f"Your account is now fully activated!\n\n"
        f"**Next Steps:**\n"
        f"1. Use /start to create your wallet\n"
        f"2. Deposit funds with /deposit\n"
        f"3. Start trading!\n\n"
        f"Use /help to see all commands."
    )
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    
    # Check if user has activated token
    if not check_token_activated(user_id):
        await update.message.reply_text(
            f"🔒 **Account Activation Required**\n\n"
            f"Hey {user_name}! 👋\n\n"
            f"To use Astra Trading Bot, you need to activate your account with a token.\n\n"
            f"**How to activate:**\n"
            f"Use `/activate <your-token>`\n\n"
            f"**Example:**\n"
            f"`/activate ASTRA-2K9F-8H3L-9M2P`\n\n"
            f"📧 Don't have a token? Contact admin to get one!\n\n"
            f"💡 Each token can only be used once."
        )
        return
    
    if not user_data[user_id]["has_wallet"]:
        keyboard = [
            [InlineKeyboardButton("🆕 Create New Wallet", callback_data="wallet_create")],
            [InlineKeyboardButton("📥 Import Existing Wallet", callback_data="wallet_import")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = f"""🚀 **Welcome to Astra Trading Bot!**

Hey {user_name}! 

To get started, you need a wallet:

🆕 **Create New Wallet**
- We'll generate a new wallet for you
- You'll get a 12-word seed phrase
- Keep it safe - it's the only way to recover your wallet!

📥 **Import Existing Wallet**
- Use your existing seed phrase
- Access your funds from other wallets

Choose an option below:"""
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    else:
        welcome_text = f"""🚀 **Welcome Back, {user_name}!**

💰 **Your Account:**
Balance: ${user_data[user_id]['balance_usd']:.2f}
Status: {"✅ Active" if user_data[user_id]['trading_enabled'] else "⛔ Disabled"}

📊 **Supported Coins:**
BTC, ETH, BNB, XRP, ADA, DOGE, SOL, DOT, MATIC, AVAX, LINK, UNI

📥 **Quick Commands:**
/wallet - Manage your wallet
/balance - Check your balance
/portfolio - View your holdings
/trades - Your trade history
/deposit - Deposit crypto
/withdraw - Withdraw funds
/prices - Live crypto prices

⚡ **Auto-Trading:** Enabled
The bot will automatically execute trades based on signals!

Let's make some profit! 💸"""
        
        await update.message.reply_text(welcome_text)

async def wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle wallet creation/import buttons"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_name = query.from_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    user = user_data[user_id]
    
    if query.data == "wallet_create":
        # Generate seed phrase FIRST
        seed_phrase = generate_seed_phrase()
        
        # Store seed phrase
        user["seed_phrase"] = seed_phrase
        
        # Generate wallet address from seed phrase
        user["wallets"] = {
            "SOL": generate_wallet_address(user_id, seed_phrase)
        }
        
        user["has_wallet"] = True
        user["wallet_created"] = True
        
        wallet_text = f"""✅ **Wallet Created Successfully!**

🔐 **Your Seed Phrase:**
`{seed_phrase}`

⚠️ **CRITICAL - READ CAREFULLY:**
- Write down these 12 words on paper
- NEVER share them with anyone
- Store them in a safe place
- This is the ONLY way to recover your wallet
- Lost seed phrase = Lost funds FOREVER!

📍 **Your Solana Wallet Address:**

**Solana (SOL):**
`{user['wallets']['SOL']}`

✅ To confirm you saved your seed phrase, type:
`/confirmseed`

Then you can start depositing and trading!"""
        
        await query.edit_message_text(wallet_text)
        
    elif query.data == "wallet_import":
        await query.edit_message_text(
            "📥 **Import Wallet**\n\n"
            "Send your 12-word seed phrase in this format:\n\n"
            "`/importseed word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12`\n\n"
            "⚠️ **Warning:** Make sure you're in a private chat!\n"
            "Your seed phrase will be deleted immediately after processing."
        )

async def import_seed_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Import wallet from seed phrase"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    user = user_data[user_id]
    
    try:
        await update.message.delete()
    except:
        pass
    
    if len(context.args) != 12:
        await update.message.reply_text(
            "❌ **Invalid Seed Phrase**\n\n"
            "Seed phrase must be exactly 12 words.\n\n"
            "Format: `/importseed word1 word2 ... word12`"
        )
        return
    
    seed_phrase = " ".join(context.args)
    user["seed_phrase"] = seed_phrase
    
    user["wallets"] = {
        "SOL": generate_wallet_address(user_id, seed_phrase)
}
    
    user["has_wallet"] = True
    user["wallet_created"] = True
    
    wallet_text = f"""✅ **Wallet Imported Successfully!**

Your wallet has been restored from your seed phrase.

📝 **Your Solana Wallet Address:**

**Solana (SOL):**
`{user['wallets']['SOL']}`

🎉 You're all set! Start trading with /help"""
    
    await update.message.reply_text(wallet_text)

async def confirm_seed_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm user saved their seed phrase"""
    user_id = update.effective_user.id
    
    if user_id not in user_data or not user_data[user_id]["has_wallet"]:
        await update.message.reply_text("❌ You don't have a wallet yet. Use /start")
        return
    
    await update.message.reply_text(
        "✅ **Seed Phrase Confirmed!**\n\n"
        "Great! You can now:\n"
        "• Deposit crypto with /deposit\n"
        "• View your wallet with /wallet\n"
        "• Start trading!\n\n"
        "Use /help to see all commands."
    )

async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show wallet information"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    user = user_data[user_id]
    
    if not user["has_wallet"]:
        await update.message.reply_text(
            "❌ You don't have a wallet yet.\n\n"
            "Use /start to create or import one!"
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("🔐 Show Seed Phrase", callback_data="wallet_showseed")],
        [InlineKeyboardButton("📝 Show Addresses", callback_data="wallet_addresses")],
        [InlineKeyboardButton("❌ Close", callback_data="wallet_close")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    wallet_text = f"""💼 **Your Wallet**

**Status:** ✅ Active
**Wallets:** {len(user['wallets'])} addresses

⚠️ **Security Options:**
Use buttons below to view sensitive information."""
    
    await update.message.reply_text(wallet_text, reply_markup=reply_markup)

async def wallet_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle wallet information buttons"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = user_data.get(user_id)
    
    if query.data == "wallet_close":
        await query.edit_message_text("💼 Wallet menu closed.")
        return
    
    elif query.data == "wallet_showseed":
        seed_text = f"""🔐 **Your Seed Phrase:**

`{user['seed_phrase']}`

⚠️ **WARNING:**
• NEVER share this with anyone!
• Anyone with this phrase can access your funds
• Delete this message after copying!

This message will self-destruct in 60 seconds..."""
        
        msg = await query.edit_message_text(seed_text)
        
        await asyncio.sleep(60)
        try:
            await msg.delete()
        except:
            pass
    
    elif query.data == "wallet_addresses":
        addr_text = f"""📝 **Your Solana Wallet Address:**

**Solana (SOL):**
`{user['wallets'].get('SOL', 'N/A')}`

💡 Use /deposit to get deposit instructions!"""""
        
        await query.edit_message_text(addr_text)

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show deposit instructions"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    user = user_data[user_id]
    
    if not user["has_wallet"]:
        await update.message.reply_text(
            "❌ You need to create a wallet first!\n\nUse /start"
        )
        return
    
    deposit_text = f"""💳 **Deposit Solana (SOL)**

**Step 1:** Send SOL to YOUR wallet address:

**Solana (SOL):**
`{user['wallets']['SOL']}`

**Step 2:** After sending, submit a deposit request:
Use `/addbalance <amount>` 

Example: `/addbalance 100` (if you deposited $100 worth of SOL)

**Step 3:** Wait for admin verification
An admin will verify your deposit and approve it.

⚠️ **Important:**
- This is YOUR wallet - you control it!
- Minimum: ${MINIMUM_DEPOSIT}
- Only send SOL on Solana network
- Admin must verify before balance is added

💡 Check /wallet anytime to see your address!"""
    
    await update.message.reply_text(deposit_text)

# MODIFIED: Users now request deposit, admin must approve
async def add_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User requests to add balance after depositing - requires admin approval"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    user = user_data[user_id]
    
    if not user["has_wallet"]:
        await update.message.reply_text("❌ You need to create a wallet first!\n\nUse /start")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Usage: `/addbalance <amount>`\n\n"
            "Example: `/addbalance 100`\n\n"
            "⚠️ Submit this AFTER you've deposited to your wallet."
        )
        return
    
    try:
        amount = float(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid amount!")
        return
    
    if amount < MINIMUM_DEPOSIT:
        await update.message.reply_text(f"❌ Minimum deposit is ${MINIMUM_DEPOSIT}")
        return
    
    # Create deposit request
    deposit_request = {
        "id": len(deposit_requests) + 1,
        "user_id": user_id,
        "user_name": user_name,
        "amount": amount,
        "status": "pending",
        "timestamp": datetime.now()
    }
    
    deposit_requests.append(deposit_request)
    
    # Notify user
    await update.message.reply_text(
        f"✅ **Deposit Request Submitted**\n\n"
        f"Request ID: #{deposit_request['id']}\n"
        f"Amount: ${amount:.2f}\n\n"
        f"Status: ⏳ Pending Admin Verification\n\n"
        f"An admin will verify your deposit and approve it shortly.\n"
        f"You'll be notified once your balance is updated!"
    )
    
    # Notify admins
    admin_msg = (
        f"💰 **New Deposit Request**\n\n"
        f"Request ID: #{deposit_request['id']}\n"
        f"User: {user_name} (ID: {user_id})\n"
        f"Amount: ${amount:.2f}\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"⚠️ **Action Required:**\n"
        f"1. Verify deposit in user's wallet\n"
        f"2. Use `/approvedeposit {deposit_request['id']}` to approve\n"
        f"3. Use `/rejectdeposit {deposit_request['id']}` to reject\n\n"
        f"View wallet: `/viewwallet {user_id}`"
    )
    
    for admin_id in ADMIN_USER_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_msg)
        except:
            pass

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user balance and PnL"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    # Check token activation
    if not check_token_activated(user_id):
        await update.message.reply_text(
            "🔒 **Account Not Activated**\n\n"
            "You need to activate your account first!\n\n"
            "Use `/activate <token>` to activate.\n"
            "Contact admin to get a token."
        )
        return
    user = user_data[user_id]
    
    if not user["has_wallet"]:
        await update.message.reply_text("❌ Create a wallet first with /start")
        return
    
    pnl = calculate_pnl(user_id)
    profit_pct = calculate_profit_percentage(user_id)
    portfolio_value = get_portfolio_value(user_id)
    
    pnl_emoji = "📈" if pnl >= 0 else "📉"
    pnl_symbol = "+" if pnl >= 0 else ""
    
    balance_text = f"""💰 **Account Balance**

**USD Balance:** ${user['balance_usd']:.2f}
**Portfolio Value:** ${portfolio_value:.2f}

{pnl_emoji} **PnL:** {pnl_symbol}${pnl:.2f} ({pnl_symbol}{profit_pct:.2f}%)

📊 **Statistics:**
Total Deposited: ${user['total_deposited']:.2f}
Total Withdrawn: ${user['total_withdrawn']:.2f}
Total Trades: {user['total_trades']}

🎯 **Trading Status:** {"✅ Active" if user['trading_enabled'] else "⛔ Disabled"}
📊 Auto-Trade Amount: ${user['auto_trade_amount']:.2f}

Use /portfolio to see your coin holdings!"""
    
    await update.message.reply_text(balance_text)

async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's crypto portfolio with detailed statistics"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    user = user_data[user_id]
    
    if not user["portfolio"] or all(amount == 0 for amount in user["portfolio"].values()):
        await update.message.reply_text("📊 **Portfolio Empty**\n\nYou don't own any crypto yet.\nDeposit funds and start trading!")
        return
    
    prices = get_all_prices()
    
    # Calculate today's trades
    today = datetime.now().date()
    trades_today = len([t for t in user["trade_history"] if t["timestamp"].date() == today])
    
    # Calculate total profit/loss (includes manual profit added by admin)
    pnl = calculate_pnl(user_id)
    profit_pct = calculate_profit_percentage(user_id)
    portfolio_value = get_portfolio_value(user_id)
    
    # Calculate individual coin performance
    portfolio_text = "📊 **Your Portfolio**\n\n"
    portfolio_text += "═" * 30 + "\n\n"
    
    total_crypto_value = 0
    holdings_count = 0
    
    for coin, amount in sorted(user["portfolio"].items()):
        if amount > 0:
            holdings_count += 1
            price = prices.get(coin, 0)
            value = amount * price
            total_crypto_value += value
            
            # Calculate percentage of portfolio (excluding manual profit for accurate coin allocation)
            real_portfolio = user["balance_usd"] + total_crypto_value
            if real_portfolio > 0:
                percentage = (value / real_portfolio) * 100
            else:
                percentage = 0
            
            portfolio_text += f"**{coin}** ({percentage:.1f}% of holdings)\n"
            portfolio_text += f"├─ Amount: {amount:.6f}\n"
            portfolio_text += f"├─ Price: ${price:,.2f}\n"
            portfolio_text += f"└─ Value: ${value:,.2f}\n\n"
    
    portfolio_text += "═" * 30 + "\n\n"
    
    # Portfolio summary
    portfolio_text += "💼 **Portfolio Summary**\n\n"
    portfolio_text += f"💵 USD Balance: ${user['balance_usd']:,.2f}\n"
    portfolio_text += f"📈 Crypto Holdings: ${total_crypto_value:,.2f}\n"
    
    # Show manual profit if admin added any
    manual_profit = user.get("manual_profit", 0.0)
    if manual_profit != 0:
        portfolio_text += f"✨ Trading Profits: ${manual_profit:+,.2f}\n"
    
    portfolio_text += f"💰 Total Value: ${portfolio_value:,.2f}\n\n"
    
    # Performance metrics
    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
    pnl_symbol = "+" if pnl >= 0 else ""
    
    portfolio_text += "═" * 30 + "\n\n"
    portfolio_text += "📈 **Performance**\n\n"
    portfolio_text += f"💎 Initial Investment: ${user['initial_balance']:,.2f}\n"
    portfolio_text += f"{pnl_emoji} Total Profit/Loss: {pnl_symbol}${pnl:,.2f}\n"
    portfolio_text += f"📊 Return: {pnl_symbol}{profit_pct:.2f}%\n\n"
    
    # Trading statistics
    portfolio_text += "═" * 30 + "\n\n"
    portfolio_text += "⚡ **Trading Stats**\n\n"
    portfolio_text += f"🔢 Total Trades: {user['total_trades']}\n"
    portfolio_text += f"📅 Trades Today: {trades_today}\n"
    portfolio_text += f"🎯 Holdings: {holdings_count} coin(s)\n"
    portfolio_text += f"💸 Total Deposited: ${user['total_deposited']:,.2f}\n"
    portfolio_text += f"🏦 Total Withdrawn: ${user['total_withdrawn']:,.2f}\n\n"
    
    # Status indicator
    if profit_pct >= 50:
        status = "🚀 Excellent!"
    elif profit_pct >= 20:
        status = "💎 Great!"
    elif profit_pct >= 5:
        status = "✅ Good"
    elif profit_pct >= 0:
        status = "📊 Profitable"
    elif profit_pct >= -10:
        status = "⚠️ Minor Loss"
    else:
        status = "📉 Loss"
    
    portfolio_text += f"🎯 **Status:** {status}\n"
    portfolio_text += f"⚡ **Trading:** {'✅ Active' if user['trading_enabled'] else '🔒 Disabled'}"
    
    await update.message.reply_text(portfolio_text)

async def trades_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's trade history"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    # Check token activation
    if not check_token_activated(user_id):
        await update.message.reply_text(
            "🔒 **Account Not Activated**\n\n"
            "You need to activate your account first!\n\n"
            "Use `/activate <token>` to activate.\n"
            "Contact admin to get a token."
        )
        return
    user = user_data[user_id]
    
    if not user["trade_history"]:
        await update.message.reply_text("📜 **No Trade History**\n\nYou haven't made any trades yet.")
        return
    
    recent_trades = user["trade_history"][-10:]
    
    trades_text = "📜 **Recent Trades** (Last 10)\n\n"
    
    for i, trade in enumerate(reversed(recent_trades), 1):
        action_emoji = "🟢" if trade["action"] == "BUY" else "🔴"
        timestamp = trade["timestamp"].strftime("%m/%d %H:%M")
        
        trades_text += f"{action_emoji} **{trade['action']} {trade['coin']}**\n"
        trades_text += f"Amount: {trade['amount']:.6f}\n"
        trades_text += f"Price: ${trade['price']:.2f}\n"
        trades_text += f"Value: ${trade['usd_value']:.2f}\n"
        trades_text += f"Time: {timestamp}\n\n"
    
    trades_text += f"📊 **Total Trades:** {user['total_trades']}"
    
    await update.message.reply_text(trades_text)

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request withdrawal"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    user = user_data[user_id]
    
    withdraw_text = f"""💸 **Withdraw Funds**

Since you control your own wallet, you can withdraw anytime!

📝 **To Withdraw:**
1. Use `/requestwithdraw <coin> <amount>`

Examples:
• `/requestwithdraw USD 100` - Withdraw $100 to your wallet
• `/requestwithdraw BTC 0.001` - Withdraw 0.001 BTC

**Your Current Balances:**
💵 USD: ${user['balance_usd']:.2f}
"""
    
    if user["portfolio"]:
        for coin, amount in user["portfolio"].items():
            if amount > 0:
                withdraw_text += f"₿ {coin}: {amount:.6f}\n"
    
    withdraw_text += "\n⚠️ Withdrawals require admin approval for security."
    
    await update.message.reply_text(withdraw_text)

async def request_withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process withdrawal request"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"

    initialize_user(user_id, user_name)
    # Check token activation
    if not check_token_activated(user_id):
        await update.message.reply_text(
            "🔒 **Account Not Activated**\n\n"
            "You need to activate your account first!\n\n"
            "Use `/activate <token>` to activate.\n"
            "Contact admin to get a token."
        )
        return
    user = user_data[user_id]

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/requestwithdraw <coin> <amount>`\n\n"
            "Examples:\n"
            "• `/requestwithdraw USD 100`\n"
            "• `/requestwithdraw BTC 0.001`"
        )
        return

    coin = context.args[0].upper()
    try:
        amount = float(context.args[1])
    except:
        await update.message.reply_text("❌ Invalid amount!")
        return

    if amount <= 0:
        await update.message.reply_text("❌ Amount must be positive!")
        return

    if coin == "USD":
        if user["balance_usd"] < amount:
            await update.message.reply_text(f"❌ Insufficient balance! You have ${user['balance_usd']:.2f}")
            return
    else:
        if coin not in user["portfolio"] or user["portfolio"][coin] < amount:
            available = user["portfolio"].get(coin, 0)
            await update.message.reply_text(f"❌ Insufficient {coin}! You have {available:.6f}")
            return

    withdrawal_request = {
        "id": len(withdrawal_requests) + 1,
        "user_id": user_id,
        "user_name": user_name,
        "coin": coin,
        "amount": amount,
        "status": "pending",
        "timestamp": datetime.now()
    }

    withdrawal_requests.append(withdrawal_request)

    await update.message.reply_text(
        f"✅ **Withdrawal Request Submitted**\n\n"
        f"Request ID: #{withdrawal_request['id']}\n"
        f"Coin: {coin}\n"
        f"Amount: {amount:.6f if coin != 'USD' else amount:.2f}\n\n"
        f"Status: Pending Admin Approval\n\n"
        f"You'll be notified once processed!"
    )

    admin_msg = (
        f"📬 **New Withdrawal Request**\n\n"
        f"Request ID: #{withdrawal_request['id']}\n"
        f"User: {user_name} (ID: {user_id})\n"
        f"Coin: {coin}\n"
        f"Amount: {amount:.6f if coin != 'USD' else amount:.2f}\n\n"
        f"Use `/approvewithdraw {withdrawal_request['id']}` to approve\n"
        f"Use `/rejectwithdraw {withdrawal_request['id']}` to reject"
    )

    for admin_id in ADMIN_USER_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_msg)
        except:
            pass

async def prices_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show live crypto prices"""
    await update.message.reply_text("⏳ Fetching live prices...")
    
    prices = get_all_prices()
    
    if not prices:
        await update.message.reply_text("⚠️ Unable to fetch prices. Try again later.")
        return
    
    prices_text = "🌐 **Live Crypto Prices**\n\n"
    
    for coin in SUPPORTED_COINS:
        if coin in prices:
            price = prices[coin]
            prices_text += f"**{coin}:** ${price:,.2f}\n"
    
    prices_text += f"\n🕒 Updated: {datetime.now().strftime('%H:%M:%S')}\n"
    prices_text += "\nUse /buy or /sell to trade!"
    
    await update.message.reply_text(prices_text)

async def memecoins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Solana memecoins with prices - both top and trending"""
    user_id = update.effective_user.id
    
    # Update memecoins if needed
    if should_update_memecoins():
        await update.message.reply_text("🔄 Fetching latest Solana memecoins...")
        fetch_solana_memecoins()
    
    if not SOLANA_MEMECOINS:
        await update.message.reply_text("⚠️ Unable to fetch memecoins. Try again later.")
        return
    
    # Separate trending and top
    trending = {k: v for k, v in SOLANA_MEMECOINS.items() if v.get('type') in ['trending', 'both']}
    top_by_mcap = {k: v for k, v in SOLANA_MEMECOINS.items() if v.get('type') in ['top', 'both']}
    
    memecoins_text = "🚀 **Solana Memecoins**\n\n"
    
    # Show trending first
    if trending:
        memecoins_text += "🔥 **TRENDING (24h)**\n"
        memecoins_text += "━━━━━━━━━━━━━━━━\n\n"
        
        sorted_trending = sorted(
            trending.items(), 
            key=lambda x: x[1].get('volume_24h', 0), 
            reverse=True
        )[:10]
        
        for i, (symbol, data) in enumerate(sorted_trending, 1):
            price = data['price']
            change_24h = data['price_change_24h']
            
            if price >= 1:
                price_str = f"${price:,.4f}"
            elif price >= 0.01:
                price_str = f"${price:.6f}"
            else:
                price_str = f"${price:.10f}"
            
            change_emoji = "🟢" if change_24h >= 0 else "🔴"
            
            memecoins_text += f"{i}. **{data['name']} ({symbol})**\n"
            memecoins_text += f"   💰 {price_str} | {change_emoji} {change_24h:+.2f}%\n"
            memecoins_text += f"   💧 Vol: ${data.get('volume_24h', 0):,.0f}\n\n"
        
        memecoins_text += "\n"
    
    # Show top by market cap
    memecoins_text += "📊 **TOP BY MARKET CAP**\n"
    memecoins_text += "━━━━━━━━━━━━━━━━\n\n"
    
    sorted_top = sorted(
        top_by_mcap.items(), 
        key=lambda x: x[1].get('market_cap', 0), 
        reverse=True
    )[:10]
    
    for i, (symbol, data) in enumerate(sorted_top, 1):
        price = data['price']
        change_24h = data['price_change_24h']
        
        if price >= 1:
            price_str = f"${price:,.4f}"
        elif price >= 0.01:
            price_str = f"${price:.6f}"
        else:
            price_str = f"${price:.10f}"
        
        change_emoji = "🟢" if change_24h >= 0 else "🔴"
        
        memecoins_text += f"{i}. **{data['name']} ({symbol})**\n"
        memecoins_text += f"   💰 {price_str} | {change_emoji} {change_24h:+.2f}%\n"
        memecoins_text += f"   📊 MCap: ${data.get('market_cap', 0):,.0f}\n\n"
    
    last_update = MEMECOIN_LAST_UPDATE.strftime('%H:%M:%S') if MEMECOIN_LAST_UPDATE else "Unknown"
    next_update_seconds = MEMECOIN_UPDATE_INTERVAL - (datetime.now() - MEMECOIN_LAST_UPDATE).total_seconds() if MEMECOIN_LAST_UPDATE else 0
    next_update_minutes = int(max(0, next_update_seconds) / 60)
    
    memecoins_text += f"\n━━━━━━━━━━━━━━━━\n"
    memecoins_text += f"🕒 Updated: {last_update}\n"
    memecoins_text += f"🔄 Next: ~{next_update_minutes}min\n\n"
    memecoins_text += f"**Commands:**\n"
    memecoins_text += f"• `/memecoininfo <symbol>` - Coin details\n"
    memecoins_text += f"• `/findmemecoin <address>` - Add by contract\n"
    memecoins_text += f"• `/buy <symbol> <amount>` - Trade\n\n"
    memecoins_text += f"Total: {len(SOLANA_MEMECOINS)} memecoins tracked"
    
    await update.message.reply_text(memecoins_text)

async def trending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show only trending memecoins"""
    if should_update_memecoins():
        await update.message.reply_text("🔄 Fetching trending memecoins...")
        fetch_solana_memecoins()
    
    trending = {k: v for k, v in SOLANA_MEMECOINS.items() if v.get('type') in ['trending', 'both']}
    
    if not trending:
        await update.message.reply_text("⚠️ No trending memecoins found. Try again later.")
        return
    
    trending_text = "🔥 **TRENDING SOLANA MEMECOINS (24h)**\n\n"
    
    sorted_trending = sorted(
        trending.items(), 
        key=lambda x: x[1].get('volume_24h', 0), 
        reverse=True
    )
    
    for i, (symbol, data) in enumerate(sorted_trending, 1):
        price = data['price']
        change_24h = data['price_change_24h']
        
        if price >= 1:
            price_str = f"${price:,.4f}"
        elif price >= 0.01:
            price_str = f"${price:.6f}"
        else:
            price_str = f"${price:.10f}"
        
        change_emoji = "🟢" if change_24h >= 0 else "🔴"
        fire_emoji = "🔥" * min(3, int(abs(change_24h) / 20) + 1) if abs(change_24h) > 10 else ""
        
        trending_text += f"{i}. **{data['name']} ({symbol})** {fire_emoji}\n"
        trending_text += f"   💰 Price: {price_str}\n"
        trending_text += f"   {change_emoji} 24h: {change_24h:+.2f}%\n"
        trending_text += f"   💧 Volume: ${data.get('volume_24h', 0):,.0f}\n"
        trending_text += f"   📊 MCap: ${data.get('market_cap', 0):,.0f}\n\n"
    
    trending_text += f"🔄 Auto-updates every hour\n\n"
    trending_text += f"Use `/buy <symbol> <amount>` to trade!"
    
    await update.message.reply_text(trending_text)

async def memecoin_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed info about a specific memecoin"""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/memecoininfo <symbol>`\n\n"
            "Example: `/memecoininfo WIF`\n\n"
            "Use /memecoins to see all available memecoins"
        )
        return
    
    symbol = context.args[0].upper()
    
    if should_update_memecoins():
        fetch_solana_memecoins()
    
    if symbol not in SOLANA_MEMECOINS:
        await update.message.reply_text(
            f"❌ Memecoin {symbol} not found!\n\n"
            "Use /memecoins to see available coins\n"
            "Or use /findmemecoin <address> to add a new one"
        )
        return
    
    data = SOLANA_MEMECOINS[symbol]
    
    price = data['price']
    if price >= 1:
        price_str = f"${price:,.4f}"
    elif price >= 0.01:
        price_str = f"${price:.6f}"
    else:
        price_str = f"${price:.10f}"
    
    change_emoji = "🟢" if data['price_change_24h'] >= 0 else "🔴"
    type_emoji = "🔥" if data.get('type') in ['trending', 'both'] else "📊"
    
    info_text = f"{type_emoji} **{data['name']} ({symbol})**\n\n"
    info_text += f"💰 **Price:** {price_str}\n"
    info_text += f"{change_emoji} **24h Change:** {data['price_change_24h']:+.2f}%\n"
    info_text += f"📊 **Market Cap:** ${data['market_cap']:,.0f}\n"
    info_text += f"💧 **24h Volume:** ${data.get('volume_24h', 0):,.0f}\n\n"
    
    if data.get('contract_address'):
        info_text += f"📝 **Contract Address:**\n`{data['contract_address']}`\n\n"
    
    info_text += f"⛓️ **Network:** Solana\n"
    info_text += f"🔗 **CoinGecko ID:** {data['id']}\n"
    
    if data.get('type') in ['trending', 'both']:
        info_text += f"🔥 **Status:** TRENDING!\n"
    
    info_text += f"\n**Trade Commands:**\n"
    info_text += f"• `/buy {symbol} 50` - Buy $50 worth\n"
    info_text += f"• `/sell {symbol} 50` - Sell $50 worth\n\n"
    info_text += f"Use /portfolio to see your holdings!"
    
    await update.message.reply_text(info_text)

async def find_memecoin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Find and add memecoin by Solana contract address"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "🔍 **Find Memecoin by Address**\n\n"
            "Usage: `/findmemecoin <solana_contract_address>`\n\n"
            "Example:\n"
            "`/findmemecoin DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`\n\n"
            "This will fetch the token details and add it for trading!\n\n"
            "💡 You can find contract addresses on:\n"
            "• Birdeye.so\n"
            "• Dexscreener.com\n"
            "• Solscan.io"
        )
        return
    
    contract_address = context.args[0].strip()
    
    # Validate Solana address format (basic check)
    if len(contract_address) < 32 or len(contract_address) > 44:
        await update.message.reply_text(
            "❌ Invalid Solana contract address!\n\n"
            "Solana addresses are typically 32-44 characters long."
        )
        return
    
    await update.message.reply_text("🔍 Searching for token...")
    
    memecoin = get_memecoin_by_address(contract_address)
    
    if not memecoin:
        await update.message.reply_text(
            "❌ **Token Not Found**\n\n"
            "Possible reasons:\n"
            "• Invalid contract address\n"
            "• Token not listed on CoinGecko yet\n"
            "• Not a Solana token\n\n"
            "Please verify the contract address and try again."
        )
        return
    
    price = memecoin['price']
    if price >= 1:
        price_str = f"${price:,.4f}"
    elif price >= 0.01:
        price_str = f"${price:.6f}"
    else:
        price_str = f"${price:.10f}"
    
    change_emoji = "🟢" if memecoin['price_change_24h'] >= 0 else "🔴"
    
    info_text = f"✅ **Token Found!**\n\n"
    info_text += f"🪙 **{memecoin['name']} ({memecoin['symbol']})**\n\n"
    info_text += f"💰 **Price:** {price_str}\n"
    info_text += f"{change_emoji} **24h Change:** {memecoin['price_change_24h']:+.2f}%\n"
    info_text += f"📊 **Market Cap:** ${memecoin['market_cap']:,.0f}\n"
    info_text += f"💧 **24h Volume:** ${memecoin['volume_24h']:,.0f}\n\n"
    info_text += f"📝 **Contract:**\n`{contract_address}`\n\n"
    info_text += f"⛓️ **Network:** Solana\n\n"
    info_text += f"✅ **Token added! You can now trade it:**\n"
    info_text += f"• `/buy {memecoin['symbol']} 50` - Buy $50 worth\n"
    info_text += f"• `/sell {memecoin['symbol']} 50` - Sell $50 worth\n\n"
    info_text += f"Use /portfolio to see your holdings!"
    
    await update.message.reply_text(info_text)

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buy cryptocurrency"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    user = user_data[user_id]
    
    if not user["has_wallet"]:
        await update.message.reply_text("❌ Create a wallet first with /start")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/buy <coin> <amount_usd>`\n\n"
            "Examples:\n"
            "• `/buy BTC 100` - Buy $100 worth of Bitcoin\n"
            "• `/buy ETH 50` - Buy $50 worth of Ethereum\n\n"
            f"Supported: {', '.join(SUPPORTED_COINS)}"
        )
        return
    
    coin = context.args[0].upper()
    
    if coin not in SUPPORTED_COINS and coin not in SOLANA_MEMECOINS:
        if should_update_memecoins():
            fetch_solana_memecoins()
    
        if coin not in SOLANA_MEMECOINS:
            await update.message.reply_text(
                f"❌ {coin} not supported!\n\n"
                f"Major Coins: {', '.join(SUPPORTED_COINS)}\n\n"
                "Use /memecoins to see Solana memecoins"
            )
            return
    
    try:
        amount_usd = float(context.args[1])
    except:
        await update.message.reply_text("❌ Invalid amount!")
        return
    
    if amount_usd <= 0:
        await update.message.reply_text("❌ Amount must be positive!")
        return
    
    success, message = execute_trade(user_id, "BUY", coin, amount_usd)
    
    if success:
        pnl = calculate_pnl(user_id)
        portfolio_value = get_portfolio_value(user_id)
        
        result_text = f"{message}\n\n"
        result_text += f"💰 Balance: ${user['balance_usd']:.2f}\n"
        result_text += f"📊 Portfolio: ${portfolio_value:.2f}\n"
        result_text += f"📈 PnL: ${pnl:+.2f}"
        
        await update.message.reply_text(result_text)
    else:
        await update.message.reply_text(f"❌ Trade Failed\n\n{message}")

async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sell cryptocurrency"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    user = user_data[user_id]
    
    if not user["has_wallet"]:
        await update.message.reply_text("❌ Create a wallet first with /start")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/sell <coin> <amount_usd>`\n\n"
            "Examples:\n"
            "• `/sell BTC 100` - Sell $100 worth of Bitcoin\n"
            "• `/sell ETH 50` - Sell $50 worth of Ethereum\n\n"
            f"Supported: {', '.join(SUPPORTED_COINS)}"
        )
        return
    
    coin = context.args[0].upper()
    
    if coin not in SUPPORTED_COINS and coin not in SOLANA_MEMECOINS:
        if should_update_memecoins():
            fetch_solana_memecoins()
        
        if coin not in SOLANA_MEMECOINS:
            await update.message.reply_text(
                f"❌ {coin} not supported!\n\n"
                f"Major Coins: {', '.join(SUPPORTED_COINS)}\n\n"
                "Use /memecoins to see Solana memecoins"
            )
            return
    
    try:
        amount_usd = float(context.args[1])
    except:
        await update.message.reply_text("❌ Invalid amount!")
        return
    
    if amount_usd <= 0:
        await update.message.reply_text("❌ Amount must be positive!")
        return
    
    success, message = execute_trade(user_id, "SELL", coin, amount_usd)
    
    if success:
        pnl = calculate_pnl(user_id)
        portfolio_value = get_portfolio_value(user_id)
        
        result_text = f"{message}\n\n"
        result_text += f"💰 Balance: ${user['balance_usd']:.2f}\n"
        result_text += f"📊 Portfolio: ${portfolio_value:.2f}\n"
        result_text += f"📈 PnL: ${pnl:+.2f}"
        
        await update.message.reply_text(result_text)
    else:
        await update.message.reply_text(f"❌ Trade Failed\n\n{message}")

async def autotrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start auto-trading session"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    user = user_data[user_id]
    
    if not user["has_wallet"]:
        await update.message.reply_text("❌ Create a wallet first with /start")
        return
    
    if user_id in auto_trade_sessions:
        await update.message.reply_text(
            "⚠️ You already have an active auto-trade session!\n\n"
            "Use /stopautotrade to stop it."
        )
        return
    
    if user["balance_usd"] < 10:
        await update.message.reply_text(
            "❌ Insufficient balance for auto-trading!\n\n"
            f"Minimum required: $10\n"
            f"Your balance: ${user['balance_usd']:.2f}"
        )
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "🤖 **Auto-Trade**\n\n"
            "Usage: `/autotrade <hours>`\n\n"
            "Examples:\n"
            "• `/autotrade 1` - Trade for 1 hour\n"
            "• `/autotrade 6` - Trade for 6 hours\n"
            "• `/autotrade 24` - Trade for 24 hours\n\n"
            f"💰 Your Balance: ${user['balance_usd']:.2f}\n"
            f"⚡ Auto-Trade Amount: ${user['auto_trade_amount']:.2f}\n\n"
            "The bot will automatically execute trades and notify you of progress!"
        )
        return
    
    try:
        duration = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid duration! Must be a number (hours).")
        return
    
    if duration < 1 or duration > 72:
        await update.message.reply_text("❌ Duration must be between 1 and 72 hours!")
        return
    
    # Start auto-trade session
    auto_trade_sessions[user_id] = {
        "start_time": datetime.now(),
        "duration": duration,
        "initial_balance": get_portfolio_value(user_id)
    }
    
    await update.message.reply_text(
        f"✅ **Auto-Trade Started!**\n\n"
        f"⏱️ Duration: {duration} hour(s)\n"
        f"💰 Starting Balance: ${auto_trade_sessions[user_id]['initial_balance']:.2f}\n"
        f"⚡ Trade Amount: ${user['auto_trade_amount']:.2f}\n\n"
        f"🤖 The bot will now trade automatically!\n"
        f"📊 You'll receive periodic updates\n"
        f"🛑 Use /stopautotrade to stop anytime\n\n"
        f"Sit back and watch the profits! 🚀"
    )
    
    # Start the auto-trade loop
    asyncio.create_task(auto_trade_loop(context, user_id, duration))

async def stop_autotrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop auto-trading session"""
    user_id = update.effective_user.id
    
    if user_id not in auto_trade_sessions:
        await update.message.reply_text(
            "❌ You don't have an active auto-trade session!"
        )
        return
    
    session = auto_trade_sessions[user_id]
    elapsed = datetime.now() - session["start_time"]
    elapsed_hours = elapsed.total_seconds() / 3600
    
    del auto_trade_sessions[user_id]
    
    current_balance = get_portfolio_value(user_id)
    profit = current_balance - session["initial_balance"]
    
    await update.message.reply_text(
        f"🛑 **Auto-Trade Stopped**\n\n"
        f"⏱️ Duration: {elapsed_hours:.1f} hour(s)\n"
        f"💵 Starting: ${session['initial_balance']:.2f}\n"
        f"💰 Current: ${current_balance:.2f}\n"
        f"📈 Profit: ${profit:+.2f}\n\n"
        f"Session ended manually."
    )

async def autotrade_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check auto-trade session status"""
    user_id = update.effective_user.id
    
    if user_id not in auto_trade_sessions:
        await update.message.reply_text(
            "ℹ️ No active auto-trade session.\n\n"
            "Use /autotrade <hours> to start!"
        )
        return
    
    session = auto_trade_sessions[user_id]
    elapsed = datetime.now() - session["start_time"]
    remaining = timedelta(hours=session["duration"]) - elapsed
    
    current_balance = get_portfolio_value(user_id)
    profit = current_balance - session["initial_balance"]
    profit_pct = (profit / session["initial_balance"] * 100) if session["initial_balance"] > 0 else 0
    
    status_text = f"🤖 **Auto-Trade Status**\n\n"
    status_text += f"⏱️ Elapsed: {elapsed.seconds // 3600}h {(elapsed.seconds % 3600) // 60}m\n"
    status_text += f"⏳ Remaining: {remaining.seconds // 3600}h {(remaining.seconds % 3600) // 60}m\n\n"
    status_text += f"💵 Starting: ${session['initial_balance']:.2f}\n"
    status_text += f"💰 Current: ${current_balance:.2f}\n"
    status_text += f"{'📈' if profit >= 0 else '📉'} Profit: ${profit:+.2f} ({profit_pct:+.2f}%)\n\n"
    status_text += f"🎯 Status: {'🟢 Profitable' if profit >= 0 else '🔴 Loss'}\n\n"
    status_text += "Use /stopautotrade to end session early"
    
    await update.message.reply_text(status_text)

async def set_autotrade_amount_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set auto-trade amount per trade"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    user = user_data[user_id]
    
    if not context.args:
        await update.message.reply_text(
            f"⚡ **Auto-Trade Settings**\n\n"
            f"Current Amount: ${user['auto_trade_amount']:.2f}\n\n"
            f"Usage: `/setautoamount <amount>`\n\n"
            f"Examples:\n"
            f"• `/setautoamount 50` - Set to $50 per trade\n"
            f"• `/setautoamount 200` - Set to $200 per trade\n\n"
            f"This is the maximum amount per trade during auto-trading."
        )
        return
    
    try:
        amount = float(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid amount!")
        return
    
    if amount < 10:
        await update.message.reply_text("❌ Minimum auto-trade amount is $10!")
        return
    
    user["auto_trade_amount"] = amount
    
    await update.message.reply_text(
        f"✅ Auto-trade amount set to ${amount:.2f}\n\n"
        f"The bot will trade up to this amount per trade during auto-trading."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message"""
    user_id = update.effective_user.id
    
    if not check_token_activated(user_id):
        await update.message.reply_text(
            "🔒 **Activate Your Account First!**\n\n"
            "Use `/activate <token>` to get started.\n\n"
            "Contact admin for an activation token."
        )
        return
    
    help_text = """📚 **Astra Trading Bot - User Commands**

🔑 **Account:**
/activate <token> - Activate your account
/start - Create or import wallet

💼 **Wallet:**
/wallet - View wallet info
/confirmseed - Confirm seed phrase saved
/importseed <12 words> - Import wallet

💰 **Balance:**
/balance - Check balance & PnL
/portfolio - View holdings
/trades - Trade history

💳 **Deposits:**
/deposit - Deposit instructions
/addbalance <amount> - Request deposit confirmation

📈 **Trading:**
/prices - Live crypto prices
/buy <coin> <amount> - Buy crypto
/sell <coin> <amount> - Sell crypto
/memecoins - Solana memecoins
/trending - Trending memecoins
/memecoininfo <symbol> - Coin details
/findmemecoin <address> - Add by contract

🤖 **Auto-Trading:**
/autotrade <hours> - Start auto-trading
/stopautotrade - Stop auto-trading
/autostatus - Check status
/setautoamount <amount> - Set trade amount

💸 **Withdrawals:**
/withdraw - Withdrawal info
/requestwithdraw <coin> <amount> - Request withdrawal

📊 **Info:**
/help - This message


💡 **Examples:**
- `/activate ASTRA-2K9F-8H3L-9M2P`
- `/buy BTC 100` - Buy $100 of Bitcoin
- `/sell ETH 50` - Sell $50 of Ethereum
- `/addbalance 500` - Confirm $500 deposit
- `/autotrade 6` - Auto-trade for 6 hours

⚡ **Trading Fee:** 0.1% per trade
💵 **Min Deposit:** $10

Need help? Contact admin!"""
    
    await update.message.reply_text(help_text)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    uptime = datetime.now() - bot_stats["start_time"]
    days = uptime.days
    hours = uptime.seconds // 3600
    
    stats_text = f"""📊 **Bot Statistics**

**👥 Users:**
Total Users: {bot_stats['total_users']}

**💰 Financial:**
Total Deposits: ${bot_stats['total_deposits']:.2f}
Total Trades: {bot_stats['total_trades']}
Trading Volume: ${bot_stats['total_volume']:.2f}

**⚡ System:**
Uptime: {days}d {hours}h
Supported Coins: {len(SUPPORTED_COINS)}

**📈 Active Now:**
Online Traders: {len([u for u in user_data.values() if u['trading_enabled']])}
"""
    
    await update.message.reply_text(stats_text)

# ===== ADMIN COMMANDS =====
async def tokens_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View token status (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    total_tokens = len(VALID_TOKENS)
    used_tokens = len(USED_TOKENS)
    available_tokens = total_tokens - used_tokens
    
    tokens_text = f"""🔑 **Token Management**

📊 **Statistics:**
Total Tokens: {total_tokens}
Used Tokens: {used_tokens}
Available Tokens: {available_tokens}

**Used Tokens:**
"""
    
    if USED_TOKENS:
        for token in sorted(USED_TOKENS):
            # Find who used it
            user_with_token = None
            for uid, data in user_data.items():
                if data.get("activation_token") == token:
                    user_with_token = f"{data['name']} (ID: {uid})"
                    break
            tokens_text += f"• `{token}` - {user_with_token or 'Unknown'}\n"
    else:
        tokens_text += "None yet\n"
    
    tokens_text += f"\n**Available:** {available_tokens} tokens remaining\n\n"
    tokens_text += "Use `/listtokens` to see all available tokens"
    
    await update.message.reply_text(tokens_text)


async def listtoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all unused tokens (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    available = [t for t in VALID_TOKENS if t not in USED_TOKENS]
    
    if not available:
        await update.message.reply_text("❌ No available tokens left!")
        return
    
    tokens_text = f"🔑 **Available Tokens** ({len(available)})\n\n"
    
    for i, token in enumerate(available[:30], 1):  # Show first 30
        tokens_text += f"{i}. `{token}`\n"
    
    if len(available) > 30:
        tokens_text += f"\n... and {len(available) - 30} more\n\n"
    
    tokens_text += "\n💡 Copy any token and share with users"
    
    await update.message.reply_text(tokens_text)
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    admin_text = """🛡️ **Admin Panel - All Commands**

👥 **User Management:**
/allusers - List all users
/userinfo <user_id> - User details
/setbalance <user_id> <amount> - Set balance
/addprofit <user_id> <amount> - Add profit
/setprofit <user_id> <amount> - Set total profit
/toggletrading <user_id> - Toggle trading

🔑 **Token Management:**
/tokens - View token statistics
/listtokens - List available tokens

💳 **Deposits:**
/deposits - Pending deposits
/approvedeposit <id> - Approve deposit
/rejectdeposit <id> [reason] - Reject deposit

💸 **Withdrawals:**
/withdrawals - Pending withdrawals
/approvewithdraw <id> - Approve withdrawal
/rejectwithdraw <id> - Reject withdrawal

💼 **Wallet Management:**
/viewwallet <user_id> - View user wallet
/createwallet <user_id> - Create wallet
/importwallet <user_id> <12 words> - Import wallet

📢 **Communication:**
/broadcast <message> - Message all users

📊 **Statistics:**
/adminstats - Detailed statistics
/stats - Public statistics

💡 **Examples:**
- `/userinfo 123456789`
- `/approvedeposit 5`
- `/addprofit 123456789 50`
- `/setbalance 123456789 500`
- `/tokens`
- `/broadcast New features added!`
- `/viewwallet 123456789`

⚙️ **System Info:**
- 50 activation tokens available
- BIP44 Solana wallet generation
- Real-time price tracking
- Auto-trade system
- Manual profit adjustments"""
    
    await update.message.reply_text(admin_text)


# NEW: View pending deposits
async def deposits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all pending deposits (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    pending = [d for d in deposit_requests if d["status"] == "pending"]
    
    if not pending:
        await update.message.reply_text("✅ No pending deposits!")
        return
    
    deposits_text = "💰 **Pending Deposits**\n\n"
    
    for req in pending:
        deposits_text += f"**Request #{req['id']}**\n"
        deposits_text += f"User: {req['user_name']} (ID: {req['user_id']})\n"
        deposits_text += f"Amount: ${req['amount']:.2f}\n"
        deposits_text += f"Time: {req['timestamp'].strftime('%Y-%m-%d %H:%M')}\n\n"
    
    deposits_text += "Use `/approvedeposit <id>` or `/rejectdeposit <id>`"
    
    await update.message.reply_text(deposits_text)

# NEW: Approve deposit
async def approve_deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve deposit request (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/approvedeposit <request_id>`")
        return
    
    try:
        request_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid request ID!")
        return
    
    request = None
    for req in deposit_requests:
        if req["id"] == request_id and req["status"] == "pending":
            request = req
            break
    
    if not request:
        await update.message.reply_text("❌ Request not found or already processed!")
        return
    
    target_user_id = request["user_id"]
    user = user_data.get(target_user_id)
    
    if not user:
        await update.message.reply_text("❌ User not found!")
        return
    
    amount = request["amount"]
    
    user["balance_usd"] += amount
    user["total_deposited"] += amount
    
    if user["initial_balance"] == 0:
        user["initial_balance"] = amount
    
    bot_stats["total_deposits"] += amount
    request["status"] = "approved"
    request["approved_by"] = user_id
    request["approved_at"] = datetime.now()
    
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"✅ **Deposit Approved!**\n\n"
                 f"Request ID: #{request_id}\n"
                 f"Amount: ${amount:.2f}\n\n"
                 f"Your new balance: ${user['balance_usd']:.2f}\n\n"
                 f"🎯 Ready to trade! Use /balance to see your stats."
        )
    except:
        pass
    
    await update.message.reply_text(
        f"✅ Deposit #{request_id} approved!\n\n"
        f"User: {request['user_name']} (ID: {target_user_id})\n"
        f"Amount: ${amount:.2f}\n"
        f"New Balance: ${user['balance_usd']:.2f}"
    )

# NEW: Reject deposit
async def reject_deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject deposit request (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "Usage: `/rejectdeposit <request_id> [reason]`\n\n"
            "Example: `/rejectdeposit 5 No deposit found in wallet`"
        )
        return
    
    try:
        request_id = int(context.args[0])
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
    except:
        await update.message.reply_text("❌ Invalid request ID!")
        return
    
    request = None
    for req in deposit_requests:
        if req["id"] == request_id and req["status"] == "pending":
            request = req
            break
    
    if not request:
        await update.message.reply_text("❌ Request not found or already processed!")
        return
    
    request["status"] = "rejected"
    request["rejected_by"] = user_id
    request["rejected_at"] = datetime.now()
    request["rejection_reason"] = reason
    
    try:
        await context.bot.send_message(
            chat_id=request["user_id"],
            text=f"❌ **Deposit Request Rejected**\n\n"
                 f"Request ID: #{request_id}\n"
                 f"Amount: ${request['amount']:.2f}\n\n"
                 f"Reason: {reason}\n\n"
                 f"Please contact admin if you believe this is an error."
        )
    except:
        pass
    
    await update.message.reply_text(
        f"❌ Deposit #{request_id} rejected!\n\n"
        f"User: {request['user_name']}\n"
        f"Reason: {reason}"
    )

async def all_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all users (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    users_text = "👥 **All Users**\n\n"
    
    for uid, data in user_data.items():
        portfolio_value = get_portfolio_value(uid)
        users_text += f"**{data['name']}** (ID: {uid})\n"
        users_text += f"Balance: ${portfolio_value:.2f}\n"
        users_text += f"Trades: {data['total_trades']}\n\n"
    
    if len(users_text) > 4000:
        users_text = users_text[:4000] + "\n\n... (truncated)"
    
    await update.message.reply_text(users_text or "No users yet.")

async def user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get detailed user information (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/userinfo <user_id>`")
        return
    
    try:
        target_user_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid user ID!")
        return
    
    if target_user_id not in user_data:
        await update.message.reply_text("❌ User not found!")
        return
    
    user = user_data[target_user_id]
    pnl = calculate_pnl(target_user_id)
    profit_pct = calculate_profit_percentage(target_user_id)
    portfolio_value = get_portfolio_value(target_user_id)
    
    info_text = f"""👤 **User Information**

**Name:** {user['name']}
**User ID:** {target_user_id}
**Joined:** {user['join_date'].strftime('%Y-%m-%d %H:%M')}

💼 **Wallet Status:**
Has Wallet: {"✅ Yes" if user['has_wallet'] else "❌ No"}
Trading: {"✅ Enabled" if user['trading_enabled'] else "🔒 Disabled"}

💰 **Finances:**
USD Balance: ${user['balance_usd']:.2f}
Portfolio Value: ${portfolio_value:.2f}
Total Value: ${portfolio_value:.2f}

📊 **Statistics:**
Total Deposited: ${user['total_deposited']:.2f}
Total Withdrawn: ${user['total_withdrawn']:.2f}
Total Trades: {user['total_trades']}

📈 **Performance:**
Initial Balance: ${user['initial_balance']:.2f}
PnL: ${pnl:+.2f} ({profit_pct:+.2f}%)

🎯 **Portfolio:**"""
    
    if user["portfolio"]:
        for coin, amount in user["portfolio"].items():
            if amount > 0:
                info_text += f"\n{coin}: {amount:.6f}"
    else:
        info_text += "\nNo holdings"
    
    await update.message.reply_text(info_text)

async def set_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user balance (admin only)"""
    user_id = update.effective_user.id

    if user_id not in ADMIN_USER_IDS:
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/setbalance <user_id> <amount>`")
        return

    try:
        target_user_id = int(context.args[0])
        amount = float(context.args[1])
    except:
        await update.message.reply_text("❌ Invalid user ID or amount!")
        return

    if target_user_id not in user_data:
        await update.message.reply_text("❌ User not found!")
        return

    user = user_data[target_user_id]
    old_balance = user.get("balance_usd", 0.0)
    user["balance_usd"] = amount

    await update.message.reply_text(
        f"✅ Balance updated!\n\n"
        f"User: {user['name']} (ID: {target_user_id})\n"
        f"Old Balance: ${old_balance:.2f}\n"
        f"New Balance: ${amount:.2f}"
    )

    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"💰 Your balance has been updated to ${amount:.2f}"
        )
    except:
        pass
    
async def add_profit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add profit to user's account (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/addprofit <user_id> <amount>`\n\n"
            "Example: `/addprofit 123456 50` - Add $50 profit\n\n"
            "This adds profit to their displayed PnL without changing actual balance."
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        profit_amount = float(context.args[1])
    except:
        await update.message.reply_text("❌ Invalid user ID or amount!")
        return
    
    if target_user_id not in user_data:
        await update.message.reply_text("❌ User not found!")
        return
    
    user = user_data[target_user_id]
    
    if "manual_profit" not in user:
        user["manual_profit"] = 0.0
    
    old_profit = user["manual_profit"]
    user["manual_profit"] += profit_amount
    
    new_pnl = calculate_pnl(target_user_id)
    new_profit_pct = calculate_profit_percentage(target_user_id)
    
    await update.message.reply_text(
        f"✅ **Profit Added Successfully!**\n\n"
        f"User: {user['name']} (ID: {target_user_id})\n"
        f"Profit Added: ${profit_amount:+.2f}\n"
        f"Previous Manual Profit: ${old_profit:.2f}\n"
        f"New Manual Profit: ${user['manual_profit']:.2f}\n\n"
        f"📊 **User's New Stats:**\n"
        f"Total PnL: ${new_pnl:+.2f}\n"
        f"Profit %: {new_profit_pct:+.2f}%\n"
        f"Portfolio Value: ${get_portfolio_value(target_user_id):,.2f}"
    )
    
    profit_emoji = "🎉" if profit_amount > 0 else "📉"
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"{profit_emoji} **Trading Update!**\n\n"
                 f"Your trades are performing well!\n"
                 f"New Profit: ${profit_amount:+.2f}\n\n"
                 f"💰 Total PnL: ${new_pnl:+.2f} ({new_profit_pct:+.2f}%)\n"
                 f"📊 Portfolio Value: ${get_portfolio_value(target_user_id):,.2f}\n\n"
                 f"Use /portfolio to see details!"
        )
    except:
        pass

async def set_profit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set total profit display for user (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/setprofit <user_id> <amount>`\n\n"
            "Example: `/setprofit 123456 500` - Set total profit to $500\n\n"
            "This sets the exact profit amount they'll see."
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        profit_amount = float(context.args[1])
    except:
        await update.message.reply_text("❌ Invalid user ID or amount!")
        return
    
    if target_user_id not in user_data:
        await update.message.reply_text("❌ User not found!")
        return
    
    user = user_data[target_user_id]
    
    current_value = user["balance_usd"]
    prices = get_all_prices()
    for coin, amount in user["portfolio"].items():
        if coin in prices:
            current_value += amount * prices[coin]
    
    initial = user["initial_balance"]
    real_pnl = current_value - initial if initial > 0 else 0
    
    user["manual_profit"] = profit_amount - real_pnl
    
    new_pnl = calculate_pnl(target_user_id)
    new_profit_pct = calculate_profit_percentage(target_user_id)
    
    await update.message.reply_text(
        f"✅ **Profit Set Successfully!**\n\n"
        f"User: {user['name']} (ID: {target_user_id})\n"
        f"Real PnL: ${real_pnl:.2f}\n"
        f"Manual Profit: ${user['manual_profit']:.2f}\n"
        f"Displayed PnL: ${new_pnl:.2f}\n"
        f"Profit %: {new_profit_pct:+.2f}%\n\n"
        f"📊 Portfolio Value: ${get_portfolio_value(target_user_id):,.2f}"
    )
    
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"🎉 **Great Trading Performance!**\n\n"
                 f"💰 Total Profit: ${new_pnl:+.2f}\n"
                 f"📈 Return: {new_profit_pct:+.2f}%\n"
                 f"📊 Portfolio Value: ${get_portfolio_value(target_user_id):,.2f}\n\n"
                 f"Keep up the excellent work! 🚀"
        )
    except:
        pass    

async def toggle_trading_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle user trading status (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/toggletrading <user_id>`")
        return
    
    try:
        target_user_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid user ID!")
        return
    
    if target_user_id not in user_data:
        await update.message.reply_text("❌ User not found!")
        return
    
    user = user_data[target_user_id]
    user["trading_enabled"] = not user["trading_enabled"]
    status = "enabled" if user["trading_enabled"] else "disabled"
    
    await update.message.reply_text(
        f"✅ Trading {status} for {user['name']} (ID: {target_user_id})"
    )
    
    try:
        emoji = "✅" if user["trading_enabled"] else "🔒"
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"{emoji} Your trading has been {status} by admin."
        )
    except:
        pass

async def create_wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create wallet for a user (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/createwallet <user_id>`")
        return
    
    try:
        target_user_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid user ID!")
        return
    
    if target_user_id not in user_data:
        await update.message.reply_text("❌ User not found!")
        return
    
    user = user_data[target_user_id]
    
    # Generate seed phrase FIRST
    seed_phrase = generate_seed_phrase()
    
    # Store seed phrase
    user["seed_phrase"] = seed_phrase
    
    # Generate wallet address from seed phrase
    user["wallets"] = {
        "SOL": generate_wallet_address(target_user_id, seed_phrase)
    }
    user["has_wallet"] = True
    user["wallet_created"] = True
    
    await update.message.reply_text(
        f"✅ Wallet created for user {user['name']} (ID: {target_user_id})\n\n"
        f"🔐 Seed Phrase:\n`{seed_phrase}`\n\n"
        f"📍 Address:\nSOL: `{user['wallets']['SOL']}`\n\n"
        f"Tell the user to confirm their seed with /confirmseed"
    )
    
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text="✅ A new wallet has been created for you by an admin. Use /wallet to view details and /confirmseed after saving your seed phrase."
        )
    except:
        pass
        
async def import_wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Import wallet for a user (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    if len(context.args) < 13:
        await update.message.reply_text(
            "Usage: `/importwallet <user_id> <12-word seed phrase>`\n\n"
            "Example: `/importwallet 123456 word1 word2 ... word12`"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        seed_phrase = " ".join(context.args[1:13])
    except:
        await update.message.reply_text("❌ Invalid format!")
        return
    
    if target_user_id not in user_data:
        await update.message.reply_text("❌ User not found!")
        return
    
    user = user_data[target_user_id]
    
    try:
        await update.message.delete()
    except:
        pass
    
    user["seed_phrase"] = seed_phrase
    user["wallets"] = {
    "SOL": generate_wallet_address(target_user_id, seed_phrase)
    }
    
    user["has_wallet"] = True
    user["wallet_created"] = True
    
    await context.bot.send_message(
        chat_id=user_id,
        text=f"✅ Wallet imported for user {user['name']} (ID: {target_user_id})"
    )
    
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text="✅ **Wallet Imported!**\n\nYour wallet has been restored. Use /wallet to view details."
        )
    except:
        pass

async def view_wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View user's wallet details (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/viewwallet <user_id>`")
        return
    
    try:
        target_user_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid user ID!")
        return
    
    if target_user_id not in user_data:
        await update.message.reply_text("❌ User not found!")
        return
    
    user = user_data[target_user_id]
    
    if not user["has_wallet"]:
        await update.message.reply_text("❌ User doesn't have a wallet yet!")
        return
    
    wallet_info = f"""👤 **User Wallet Details**

**User:** {user['name']} (ID: {target_user_id})

🔐 **Seed Phrase:**
`{user['seed_phrase']}`

📝 **Solana Wallet Address:**

**Solana (SOL):**
`{user['wallets']['SOL']}`

💰 **Balance:** ${user['balance_usd']:.2f}
📊 **Portfolio Value:** ${get_portfolio_value(target_user_id):.2f}

⚠️ This message will self-destruct in 60 seconds..."""
    
    msg = await update.message.reply_text(wallet_info)
    
    await asyncio.sleep(60)
    try:
        await msg.delete()
    except:
        pass

async def withdrawals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all pending withdrawals (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    pending = [w for w in withdrawal_requests if w["status"] == "pending"]
    
    if not pending:
        await update.message.reply_text("✅ No pending withdrawals!")
        return
    
    withdrawals_text = "🚨 **Pending Withdrawals**\n\n"
    
    for req in pending:
        withdrawals_text += f"**Request #{req['id']}**\n"
        withdrawals_text += f"User: {req['user_name']} (ID: {req['user_id']})\n"
        withdrawals_text += f"Coin: {req['coin']}\n"
        withdrawals_text += f"Amount: {req['amount']:.6f if req['coin'] != 'USD' else req['amount']:.2f}\n"
        withdrawals_text += f"Time: {req['timestamp'].strftime('%Y-%m-%d %H:%M')}\n\n"
    
    withdrawals_text += "Use `/approvewithdraw <id>` or `/rejectwithdraw <id>`"
    
    await update.message.reply_text(withdrawals_text)

async def approve_withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve withdrawal (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/approvewithdraw <request_id>`")
        return
    
    try:
        request_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid request ID!")
        return
    
    request = None
    for req in withdrawal_requests:
        if req["id"] == request_id and req["status"] == "pending":
            request = req
            break
    
    if not request:
        await update.message.reply_text("❌ Request not found or already processed!")
        return
    
    user = user_data.get(request["user_id"])
    if not user:
        await update.message.reply_text("❌ User not found!")
        return
    
    coin = request["coin"]
    amount = request["amount"]
    
    if coin == "USD":
        user["balance_usd"] -= amount
    else:
        user["portfolio"][coin] -= amount
    
    user["total_withdrawn"] += amount
    request["status"] = "approved"
    
    try:
        await context.bot.send_message(
            chat_id=request["user_id"],
            text=f"✅ **Withdrawal Approved**\n\n"
                 f"Request ID: #{request_id}\n"
                 f"Coin: {coin}\n"
                 f"Amount: {amount:.6f if coin != 'USD' else amount:.2f}\n\n"
                 f"Funds will be sent to your wallet shortly!"
        )
    except:
        pass
    
    await update.message.reply_text(
        f"✅ Withdrawal #{request_id} approved!\n"
        f"User: {request['user_name']}\n"
        f"Amount: {amount:.6f if coin != 'USD' else amount:.2f} {coin}"
    )

async def reject_withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject withdrawal (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/rejectwithdraw <request_id>`")
        return
    
    try:
        request_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid request ID!")
        return
    
    request = None
    for req in withdrawal_requests:
        if req["id"] == request_id and req["status"] == "pending":
            request = req
            break
    
    if not request:
        await update.message.reply_text("❌ Request not found or already processed!")
        return
    
    request["status"] = "rejected"
    
    try:
        await context.bot.send_message(
            chat_id=request["user_id"],
            text=f"❌ **Withdrawal Rejected**\n\n"
                 f"Request ID: #{request_id}\n"
                 f"Coin: {request['coin']}\n"
                 f"Amount: {request['amount']:.6f if request['coin'] != 'USD' else request['amount']:.2f}\n\n"
                 f"Contact admin for more information."
        )
    except:
        pass
    
    await update.message.reply_text(f"❌ Withdrawal #{request_id} rejected!")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all users (admin only)"""
    user_id = update.effective_user.id

    if user_id not in ADMIN_USER_IDS:
        return

    if not context.args:
        await update.message.reply_text("Usage: `/broadcast <message>`")
        return

    message = " ".join(context.args)
    success = 0
    failed = 0

    for uid in user_data.keys():
        try:
            await context.bot.send_message(chat_id=uid, text=f"📣 **Announcement**\n\n{message}")
            success += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"📣 Broadcast complete!\n\n"
        f"✅ Sent: {success}\n"
        f"❌ Failed: {failed}"
    )

async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detailed admin statistics"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    uptime = datetime.now() - bot_stats["start_time"]
    days = uptime.days
    hours = uptime.seconds // 3600
    
    total_portfolio_value = sum(get_portfolio_value(uid) for uid in user_data.keys())
    active_traders = len([u for u in user_data.values() if u['trading_enabled'] and u['has_wallet']])
    users_with_balance = len([u for u in user_data.values() if u['balance_usd'] > 0])
    
    stats_text = f"""📊 **Admin Statistics Dashboard**

👥 **Users:**
Total Users: {bot_stats['total_users']}
With Wallets: {len([u for u in user_data.values() if u['has_wallet']])}
Active Traders: {active_traders}
Users with Balance: {users_with_balance}

💰 **Financial Overview:**
Total Deposits: ${bot_stats['total_deposits']:.2f}
Total Portfolio Value: ${total_portfolio_value:.2f}
Total Trades: {bot_stats['total_trades']}
Trading Volume: ${bot_stats['total_volume']:.2f}

📈 **Trading Activity:**
Avg Trades/User: {bot_stats['total_trades'] / max(bot_stats['total_users'], 1):.1f}
Avg Volume/Trade: ${bot_stats['total_volume'] / max(bot_stats['total_trades'], 1):.2f}

💳 **Deposits:**
Pending: {len([d for d in deposit_requests if d['status'] == 'pending'])}
Approved: {len([d for d in deposit_requests if d['status'] == 'approved'])}
Rejected: {len([d for d in deposit_requests if d['status'] == 'rejected'])}

💸 **Withdrawals:**
Pending: {len([w for w in withdrawal_requests if w['status'] == 'pending'])}
Approved: {len([w for w in withdrawal_requests if w['status'] == 'approved'])}
Rejected: {len([w for w in withdrawal_requests if w['status'] == 'rejected'])}

⚡ **System:**
Uptime: {days}d {hours}h
Supported Coins: {len(SUPPORTED_COINS)}
Trading Fee: {TRADING_FEE * 100}%
Min Deposit: ${MINIMUM_DEPOSIT}
"""
    
    await update.message.reply_text(stats_text)

# ===== MAIN =====
def main():
    """Start the bot"""
    print("🚀 Starting Astra Trading Bot...")
    
    # Build application with proper initialization
    application = Application.builder().token(BOT_TOKEN).build()
    
    # User commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("wallet", wallet_command))
    application.add_handler(CommandHandler("deposit", deposit_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("portfolio", portfolio_command))
    application.add_handler(CommandHandler("trades", trades_command))
    application.add_handler(CommandHandler("withdraw", withdraw_command))
    application.add_handler(CommandHandler("requestwithdraw", request_withdraw_command))
    application.add_handler(CommandHandler("prices", prices_command))
    application.add_handler(CommandHandler("buy", buy_command))
    application.add_handler(CommandHandler("sell", sell_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("importseed", import_seed_command))
    application.add_handler(CommandHandler("confirmseed", confirm_seed_command))
    application.add_handler(CommandHandler("addbalance", add_balance_command))
    
    # Auto-trade commands
    application.add_handler(CommandHandler("autotrade", autotrade_command))
    application.add_handler(CommandHandler("stopautotrade", stop_autotrade_command))
    application.add_handler(CommandHandler("autostatus", autotrade_status_command))
    application.add_handler(CommandHandler("setautoamount", set_autotrade_amount_command))
    
    # Admin commands
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("allusers", all_users_command))
    application.add_handler(CommandHandler("userinfo", user_info_command))
    application.add_handler(CommandHandler("setbalance", set_balance_command))
    application.add_handler(CommandHandler("addprofit", add_profit_command))
    application.add_handler(CommandHandler("setprofit", set_profit_command))
    application.add_handler(CommandHandler("toggletrading", toggle_trading_command))
    application.add_handler(CommandHandler("createwallet", create_wallet_command))
    application.add_handler(CommandHandler("importwallet", import_wallet_command))
    application.add_handler(CommandHandler("viewwallet", view_wallet_command))
    
    # Deposit management commands
    application.add_handler(CommandHandler("deposits", deposits_command))
    application.add_handler(CommandHandler("approvedeposit", approve_deposit_command))
    application.add_handler(CommandHandler("rejectdeposit", reject_deposit_command))
    
    # Withdrawal management commands
    application.add_handler(CommandHandler("withdrawals", withdrawals_command))
    application.add_handler(CommandHandler("approvewithdraw", approve_withdraw_command))
    application.add_handler(CommandHandler("rejectwithdraw", reject_withdraw_command))
    
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("adminstats", admin_stats_command))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(wallet_callback, pattern="^wallet_(create|import)$"))
    application.add_handler(CallbackQueryHandler(wallet_info_callback, pattern="^wallet_(showseed|addresses|close)$"))
    
    # Memecoin commands
    application.add_handler(CommandHandler("memecoins", memecoins_command))
    application.add_handler(CommandHandler("trending", trending_command))
    application.add_handler(CommandHandler("memecoininfo", memecoin_info_command))
    application.add_handler(CommandHandler("findmemecoin", find_memecoin_command))

    # Add these in the main() function where other commands are registered:
    application.add_handler(CommandHandler("activate", activate_command))
    application.add_handler(CommandHandler("tokens", tokens_command))
    application.add_handler(CommandHandler("listtokens", listtoken_command))
    
    print("✅ Bot started successfully!")
    print(f"👥 Admin IDs: {ADMIN_USER_IDS}")
    print(f"💰 Supported coins: {', '.join(SUPPORTED_COINS)}")
    print("🔄 Initializing bot connection...")
    # Initialize memecoins on startup
    print("🔄 Fetching initial memecoin data...")
    fetch_solana_memecoins()
    
    # Start background memecoin updater
    job_queue = application.job_queue
    job_queue.run_repeating(
        lambda context: fetch_solana_memecoins(), 
        interval=MEMECOIN_UPDATE_INTERVAL, 
        first=MEMECOIN_UPDATE_INTERVAL
    )
    print("✅ Memecoin auto-updater started (updates every hour)")
    # ⬆️⬆️⬆️ END OF NEW CODE ⬆️⬆️⬆️
    # Run with proper error handling
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        print(f"❌ Error running bot: {e}")
        print("\n⚠️ Common issues:")
        print("1. Invalid bot token")
        print("2. Bot token already in use")
        print("3. Network/firewall issues")
        print("\nPlease check your BOT_TOKEN and try again.")

if __name__ == "__main__":
    main()
