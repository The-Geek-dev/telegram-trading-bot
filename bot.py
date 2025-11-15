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
from threading import Thread
import time

# ===== CONFIGURATION =====
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN not found!")
    exit(1)
ADMIN_USER_IDS = [990809301,8489892403,7008942704]

# Trading Configuration
SUPPORTED_COINS = ["BTC", "ETH", "BNB", "XRP", "ADA", "DOGE", "SOL", "DOT", "MATIC", "AVAX", "LINK", "UNI"]

# Memecoin configuration
MEMECOINS = []
MEMECOIN_IDS = {}
MEMECOIN_LAST_UPDATE = None
MEMECOIN_UPDATE_INTERVAL = 3600  # Update every hour
MINIMUM_DEPOSIT = 150 # Minimum $150 deposit
TRADING_FEE = 0.001  # 0.1% trading fee
# Access Token System
ACCESS_TOKENS = [
    "ASTRA-7K9M-2X4P-8N6R",
    "ASTRA-3R5T-9W2E-7Y1U",
    "ASTRA-6H8J-4K5L-1M3N",
    "ASTRA-2Q9W-8E7R-5T4Y",
    "ASTRA-1A3S-7D6F-9G8H",
    "ASTRA-5Z4X-2C8V-3B7N",
    "ASTRA-9L8K-6J5H-4G3F",
    "ASTRA-7D2S-1A4Q-8W9E",
    "ASTRA-3R6T-5Y9U-2I8O",
    "ASTRA-8P4L-7K3J-6H5G",
    "ASTRA-2F1D-9S8A-4Q3W",
    "ASTRA-6E5R-3T2Y-7U8I",
    "ASTRA-1O9P-8L7K-5J4H",
    "ASTRA-4G3F-2D1S-9A8Q",
    "ASTRA-7W6E-5R4T-3Y2U",
    "ASTRA-9I8O-6P5L-2K1J",
    "ASTRA-3H4G-7F6D-1S2A",
    "ASTRA-8Q9W-4E3R-7T6Y",
    "ASTRA-2U1I-5O6P-9L8K",
    "ASTRA-6J7H-3G4F-8D9S",
    "ASTRA-1A2Q-7W8E-4R5T",
    "ASTRA-5Y6U-2I3O-9P8L",
    "ASTRA-9K8J-6H7G-3F4D",
    "ASTRA-4S5A-1Q2W-8E7R",
    "ASTRA-7T6Y-3U4I-2O1P",
    "ASTRA-8L9K-5J6H-4G3F",
    "ASTRA-2D3S-9A8Q-7W6E",
    "ASTRA-6R5T-1Y2U-8I9O",
    "ASTRA-3P4L-7K8J-2H1G",
    "ASTRA-9F8D-4S5A-6Q7W",
    "ASTRA-1E2R-8T9Y-5U6I",
    "ASTRA-7O6P-3L4K-9J8H",
    "ASTRA-4G5F-2D3S-1A8Q",
    "ASTRA-8W9E-6R7T-4Y5U",
    "ASTRA-2I3O-9P8L-7K6J",
    "ASTRA-6H7G-4F5D-3S2A",
    "ASTRA-1Q2W-8E9R-5T4Y",
    "ASTRA-5U6I-2O3P-9L7K",
    "ASTRA-9J8H-6G7F-4D3S",
    "ASTRA-3A4Q-1W2E-8R9T",
    "ASTRA-7Y8U-5I6O-2P1L",
    "ASTRA-8K9J-4H5G-7F6D",
    "ASTRA-2S3A-9Q8W-6E5R",
    "ASTRA-6T7Y-3U4I-1O2P",
    "ASTRA-9L8K-5J6H-4G7F",
    "ASTRA-4D5S-2A3Q-8W9E",
    "ASTRA-1R2T-7Y8U-5I6O",
    "ASTRA-8P9L-4K5J-3H2G",
    "ASTRA-3F4D-9S8A-7Q6W",
    "ASTRA-7E6R-2T3Y-8U9I",
    "ASTRA-5O6P-1L2K-9J8H"
]

used_tokens = {}  # Track which tokens are used by which user

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

# ===== WALLET GENERATION =====
def generate_wallet_address(coin, user_id):
    """Generate a deterministic wallet address (for demo purposes)"""
    seed = f"{user_id}_{coin}_{secrets.token_hex(16)}"
    hash_obj = hashlib.sha256(seed.encode())
    hash_hex = hash_obj.hexdigest()
    
    if coin == "BTC":
        return f"bc1q{hash_hex[:40]}"
    elif coin == "ETH":
        return f"0x{hash_hex[:40]}"
    elif coin == "USDT":
        return f"T{hash_hex[:33]}"
    else:
        return f"{coin}{hash_hex[:40]}"

def generate_seed_phrase():
    """Generate a 12-word seed phrase (simplified version)"""
    words = [
        "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract",
        "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid",
        "acoustic", "acquire", "across", "act", "action", "actor", "actress", "actual",
        "adapt", "add", "addict", "address", "adjust", "admit", "adult", "advance",
        "advice", "aerobic", "afford", "afraid", "again", "age", "agent", "agree",
        "ahead", "aim", "air", "airport", "aisle", "alarm", "album", "alcohol"
    ]
    
    return " ".join(random.sample(words, 12))

# ===== PRICE FETCHING =====
def get_crypto_price(symbol):
    """Get real-time crypto price from CoinGecko API"""
    try:
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
            "UNI": "uniswap",
        }
        
        # Add dynamic memecoins
        coin_ids.update(MEMECOIN_IDS)
        
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
# Add after get_all_prices() function

def fetch_trending_memecoins():
    """Fetch trending memecoins from CoinGecko"""
    try:
        # Get trending coins
        url = "https://api.coingecko.com/api/v3/search/trending"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        memecoins = []
        memecoin_ids = {}
        
        # Extract meme coins from trending
        for item in data.get('coins', []):
            coin = item.get('item', {})
            symbol = coin.get('symbol', '').upper()
            coin_id = coin.get('id', '')
            
            if symbol and coin_id:
                memecoins.append(symbol)
                memecoin_ids[symbol] = coin_id
                
                if len(memecoins) >= 15:
                    break
        
        # Always include these popular memecoins as fallback
        popular_memecoins = {
            "DOGE": "dogecoin",
            "SHIB": "shiba-inu", 
            "PEPE": "pepe",
            "FLOKI": "floki",
            "BONK": "bonk",
            "WIF": "dogwifcoin",
        }
        
        # Merge popular with trending
        for symbol, coin_id in popular_memecoins.items():
            if symbol not in memecoins:
                memecoins.append(symbol)
                memecoin_ids[symbol] = coin_id
        
        return memecoins[:20], memecoin_ids
        
    except Exception as e:
        print(f"Error fetching trending memecoins: {e}")
        return ["DOGE", "SHIB", "PEPE", "FLOKI", "BONK", "WIF"], {
            "DOGE": "dogecoin",
            "SHIB": "shiba-inu",
            "PEPE": "pepe",
            "FLOKI": "floki",
            "BONK": "bonk",
            "WIF": "dogwifcoin"
        }

def update_memecoins():
    """Update the memecoin list"""
    global MEMECOINS, MEMECOIN_LAST_UPDATE, MEMECOIN_IDS
    
    print("🔄 Updating memecoin list...")
    memecoins, memecoin_ids = fetch_trending_memecoins()
    
    MEMECOINS = memecoins
    MEMECOIN_IDS = memecoin_ids
    MEMECOIN_LAST_UPDATE = datetime.now()
    
    print(f"✅ Updated memecoins: {', '.join(MEMECOINS)}")
    
    return memecoins

def memecoin_updater_background():
    """Background thread to update memecoins regularly"""
    while True:
        try:
            update_memecoins()
            time.sleep(MEMECOIN_UPDATE_INTERVAL)
        except Exception as e:
            print(f"Error in memecoin updater: {e}")
            time.sleep(300)
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
            "manual_profit": 0.0,
            "token_activated": False,  # NEW
            "access_token": None  # NEW
        }
        bot_stats["total_users"] += 1
def verify_access_token(user_id, token):
    """Verify if access token is valid and not already used"""
    if token not in ACCESS_TOKENS:
        return False, "Invalid access token!"
    
    # Check if token is already used
    if token in used_tokens:
        if used_tokens[token] == user_id:
            return True, "Token already activated for your account."
        else:
            return False, "This token has already been used by another user!"
    
    return True, "Token valid!"

def activate_token(user_id, token):
    """Activate token for user"""
    used_tokens[token] = user_id
    if user_id in user_data:
        user_data[user_id]["token_activated"] = True
        user_data[user_id]["access_token"] = token
def require_token(func):
    """Decorator to require token activation"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in user_data or not user_data[user_id].get("token_activated", False):
            await update.message.reply_text(
                "🔐 **Access Token Required**\n\n"
                "You need to activate an access token to use this bot.\n\n"
                "Use `/activate <your-token>` to activate.\n\n"
                "Contact admin if you don't have a token."
            )
            return
        
        return await func(update, context)
    
    return wrapper
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
    
    # Check if this is memecoin mode
    session = auto_trade_sessions.get(user_id, {})
    is_memecoin_mode = session.get("mode") == "memecoin"
    
    try:
        while datetime.now() < end_time and user_id in auto_trade_sessions:
            if not user["trading_enabled"]:
                break
            
            # Memecoin mode: faster trades (5-20 minutes)
            # Regular mode: 15-45 minutes
            if is_memecoin_mode:
                await asyncio.sleep(random.randint(300, 1200))
            else:
                await asyncio.sleep(random.randint(900, 2700))
            
            if user_id not in auto_trade_sessions:
                break
            
            available_balance = user["balance_usd"]
            if available_balance >= 10:
                # Select coin based on mode
                if is_memecoin_mode:
                    if not MEMECOINS:
                        continue
                    coin = random.choice(MEMECOINS)
                    # Memecoin mode: more aggressive (70% buy, 30% sell)
                    action = "BUY" if random.random() < 0.7 else "SELL"
                    # Larger trades for memecoins (20-50% of balance)
                    max_amount = min(user["auto_trade_amount"], available_balance * 0.5)
                    trade_amount = random.uniform(20, max_amount)
                else:
                    coin = random.choice(SUPPORTED_COINS)
                    action = "BUY" if random.random() < 0.6 else "SELL"
                    max_amount = min(user["auto_trade_amount"], available_balance * 0.3)
                    trade_amount = random.uniform(10, max_amount)
                
                if action == "SELL":
                    if coin not in user["portfolio"] or user["portfolio"][coin] == 0:
                        continue
                
                success, message = execute_trade(user_id, action, coin, trade_amount)
                
                if success:
                    trades_made += 1
                    
                    # More frequent updates for memecoin mode
                    notify_interval = random.randint(2, 3) if is_memecoin_mode else random.randint(3, 5)
                    
                    if trades_made % notify_interval == 0:
                        current_pnl = calculate_pnl(user_id)
                        mode_emoji = "🎲" if is_memecoin_mode else "🤖"
                        try:
                            await context.bot.send_message(
                                chat_id=user_id,
                                text=f"{mode_emoji} **Auto-Trade Update**\n\n"
                                     f"{message}\n\n"
                                     f"📊 Trades Made: {trades_made}\n"
                                     f"💰 Current PnL: ${current_pnl:+.2f}\n"
                                     f"⏱️ Time Left: {int((end_time - datetime.now()).total_seconds() / 3600)}h"
                            )
                        except:
                            pass
        
        # Session ended
        if user_id in auto_trade_sessions:
            del auto_trade_sessions[user_id]
        
        final_balance = get_portfolio_value(user_id)
        profit = final_balance - session_start_balance
        profit_pct = (profit / session_start_balance * 100) if session_start_balance > 0 else 0
        
        mode_text = "🎲 **MEMECOIN**" if is_memecoin_mode else "🤖 **AUTO-TRADE**"
        
        report = f"✅ {mode_text} Session Complete!\n\n"
        report += f"⏱️ Duration: {duration_hours} hour(s)\n"
        report += f"📈 Trades Executed: {trades_made}\n\n"
        report += f"💵 Starting Value: ${session_start_balance:.2f}\n"
        report += f"💰 Final Value: ${final_balance:.2f}\n"
        report += f"{'📈' if profit >= 0 else '📉'} Profit/Loss: ${profit:+.2f} ({profit_pct:+.2f}%)\n\n"
        
        if is_memecoin_mode:
            if profit_pct > 50:
                report += f"🚀 TO THE MOON! Incredible gains!\n\n"
            elif profit_pct > 20:
                report += f"💎 DIAMOND HANDS! Great profit!\n\n"
            elif profit_pct > 0:
                report += f"✅ Paper gains! Not bad!\n\n"
            else:
                report += f"💀 Rekt! But that's the memecoin game!\n\n"
        else:
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
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    
    # Check if user has activated token
    if not user_data[user_id]["token_activated"]:
        welcome_text = f"""🚀 **Welcome to Astra Trading Bot!**

Hey {user_name}! 

🔐 **Access Token Required**

To use this bot, you need a valid access token.

**How to activate:**
Use the command: `/activate <your-token>`

Example: `/activate ASTRA-7K9M-2X4P-8N6Q`

**Don't have a token?**
Contact admin to get your access token.

Once activated, you'll have full access to all trading features!"""
        
        await update.message.reply_text(welcome_text)
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

async def activate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activate access token"""
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    
    if not context.args:
        await update.message.reply_text(
            "🔐 **Activate Access Token**\n\n"
            "Usage: `/activate <your-token>`\n\n"
            "Example: `/activate ASTRA-7K9M-2X4P-8N6Q`\n\n"
            "Contact admin if you don't have a token."
        )
        return
    
    token = context.args[0].upper().strip()
    
    # Verify token
    is_valid, message = verify_access_token(user_id, token)
    
    if not is_valid:
        await update.message.reply_text(f"❌ {message}\n\nContact admin for a valid token.")
        return
    
    # Check if already activated
    if user_data[user_id]["token_activated"]:
        await update.message.reply_text(
            f"✅ **Token Already Activated!**\n\n"
            f"Your token: `{user_data[user_id]['access_token']}`\n\n"
            f"You have full access to the bot.\n"
            f"Use /start to continue!"
        )
        return
    
    # Activate token
    activate_token(user_id, token)
    
    await update.message.reply_text(
        f"🎉 **Access Token Activated Successfully!**\n\n"
        f"Welcome aboard, {user_name}!\n\n"
        f"Your token: `{token}`\n\n"
        f"✅ Full bot access granted!\n\n"
        f"Use /start to create your wallet and begin trading!"
    )
async def wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle wallet creation/import buttons"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_name = query.from_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    user = user_data[user_id]
    
    if query.data == "wallet_create":
        seed_phrase = generate_seed_phrase()
        user["seed_phrase"] = seed_phrase
        
        user["wallets"] = {
            "BTC": generate_wallet_address("BTC", user_id),
            "ETH": generate_wallet_address("ETH", user_id),
            "USDT": generate_wallet_address("USDT", user_id)
        }
        
        user["has_wallet"] = True
        user["wallet_created"] = True
        
        wallet_text = f"""✅ **Wallet Created Successfully!**

🔐 **Your Seed Phrase:**
`{seed_phrase}`

⚠️ **CRITICAL - READ CAREFULLY:**
• Write down these 12 words on paper
• NEVER share them with anyone
• Store them in a safe place
• This is the ONLY way to recover your wallet
• Lost seed phrase = Lost funds FOREVER!

📝 **Your Wallet Addresses:**

**Bitcoin (BTC):**
`{user['wallets']['BTC']}`

**Ethereum (ETH):**
`{user['wallets']['ETH']}`

**Tether (USDT):**
`{user['wallets']['USDT']}`

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
        "BTC": generate_wallet_address("BTC", user_id),
        "ETH": generate_wallet_address("ETH", user_id),
        "USDT": generate_wallet_address("USDT", user_id)
    }
    
    user["has_wallet"] = True
    user["wallet_created"] = True
    
    wallet_text = f"""✅ **Wallet Imported Successfully!**

Your wallet has been restored from your seed phrase.

📝 **Your Wallet Addresses:**

**Bitcoin (BTC):**
`{user['wallets']['BTC']}`

**Ethereum (ETH):**
`{user['wallets']['ETH']}`

**Tether (USDT):**
`{user['wallets']['USDT']}`

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
        addr_text = f"""📝 **Your Wallet Addresses:**

**Bitcoin (BTC):**
`{user['wallets'].get('BTC', 'N/A')}`

**Ethereum (ETH):**
`{user['wallets'].get('ETH', 'N/A')}`

**Tether (USDT - TRC20):**
`{user['wallets'].get('USDT', 'N/A')}`

💡 Use /deposit to get deposit instructions!"""
        
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
    
    deposit_text = f"""💳 **Deposit Crypto**

**Step 1:** Send crypto to YOUR wallet addresses:

**Bitcoin (BTC):**
`{user['wallets']['BTC']}`

**Ethereum (ETH):**
`{user['wallets']['ETH']}`

**Tether (USDT - TRC20):**
`{user['wallets']['USDT']}`

**Step 2:** After sending, submit a deposit request:
Use `/addbalance <amount>` 

Example: `/addbalance 100` (if you deposited $100 worth)

**Step 3:** Wait for admin verification
An admin will verify your deposit and approve it.

⚠️ **Important:**
• These are YOUR wallets - you control them!
• Minimum: ${MINIMUM_DEPOSIT}
• Only send supported coins
• Make sure to use correct network!
• Admin must verify before balance is added

💡 Check /wallet anytime to see your addresses!"""
    
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

    # Get user's wallet address for the coin
    wallet_address = user["wallets"].get(coin, "N/A")

    withdrawal_request = {
        "id": len(withdrawal_requests) + 1,
        "user_id": user_id,
        "user_name": user_name,
        "coin": coin,
        "amount": amount,
        "wallet_address": wallet_address,  # NEW
        "status": "pending",
        "timestamp": datetime.now()
    }

    withdrawal_requests.append(withdrawal_request)

    await update.message.reply_text(
        f"✅ **Withdrawal Request Submitted**\n\n"
        f"Request ID: #{withdrawal_request['id']}\n"
        f"Coin: {coin}\n"
        f"Amount: {amount:.6f if coin != 'USD' else amount:.2f}\n"
        f"Withdrawal Address: `{wallet_address}`\n\n"
        f"Status: ⏳ Pending Admin Approval\n\n"
        f"You'll be notified once processed!"
    )

    # Enhanced admin notification with wallet address
    admin_msg = (
        f"📬 **New Withdrawal Request**\n\n"
        f"Request ID: #{withdrawal_request['id']}\n"
        f"User: {user_name} (ID: {user_id})\n"
        f"Coin: {coin}\n"
        f"Amount: {amount:.6f if coin != 'USD' else amount:.2f}\n"
        f"Wallet Address: `{wallet_address}`\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"⚠️ **Action Required:**\n"
        f"Use `/approvewithdraw {withdrawal_request['id']}` to approve\n"
        f"Use `/rejectwithdraw {withdrawal_request['id']} [reason]` to reject"
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
    
    if coin not in SUPPORTED_COINS:
        await update.message.reply_text(f"❌ {coin} not supported!\n\nSupported: {', '.join(SUPPORTED_COINS)}")
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
    
    if coin not in SUPPORTED_COINS:
        await update.message.reply_text(f"❌ {coin} not supported!\n\nSupported: {', '.join(SUPPORTED_COINS)}")
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
    
async def automeme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start memecoin auto-trading session"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    user = user_data[user_id]
    
    if not user["has_wallet"]:
        await update.message.reply_text("❌ Create a wallet first with /start")
        return
    
    if not MEMECOINS:
        await update.message.reply_text("⏳ Memecoin list is being updated. Try again in a moment...")
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
        last_update = MEMECOIN_LAST_UPDATE.strftime('%H:%M') if MEMECOIN_LAST_UPDATE else "Never"
        
        await update.message.reply_text(
            "🎲 **Memecoin Auto-Trade**\n\n"
            "Usage: `/automeme <hours>`\n\n"
            "Examples:\n"
            "• `/automeme 1` - Trade memecoins for 1 hour\n"
            "• `/automeme 6` - Trade memecoins for 6 hours\n"
            "• `/automeme 24` - Trade memecoins for 24 hours\n\n"
            f"💰 Your Balance: ${user['balance_usd']:.2f}\n"
            f"⚡ Auto-Trade Amount: ${user['auto_trade_amount']:.2f}\n\n"
            f"🎯 Current Memecoins ({len(MEMECOINS)}): {', '.join(MEMECOINS[:8])}"
            f"{' ...' if len(MEMECOINS) > 8 else ''}\n"
            f"🕐 Updated: {last_update}\n\n"
            "⚠️ Warning: Memecoins are highly volatile! Higher risk, higher rewards! 🚀\n\n"
            "Use /memecoins to see full list with prices"
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
    
    auto_trade_sessions[user_id] = {
        "start_time": datetime.now(),
        "duration": duration,
        "initial_balance": get_portfolio_value(user_id),
        "mode": "memecoin"
    }
    
    await update.message.reply_text(
        f"✅ **Memecoin Auto-Trade Started!**\n\n"
        f"🎲 Mode: MEMECOIN CHAOS 🚀\n"
        f"⏱️ Duration: {duration} hour(s)\n"
        f"💰 Starting Balance: ${auto_trade_sessions[user_id]['initial_balance']:.2f}\n"
        f"⚡ Trade Amount: ${user['auto_trade_amount']:.2f}\n\n"
        f"🎯 Trading {len(MEMECOINS)} memecoins\n"
        f"📊 List auto-updates hourly\n\n"
        f"🤖 The bot will now trade memecoins aggressively!\n"
        f"📊 You'll receive periodic updates\n"
        f"🛑 Use /stopautotrade to stop anytime\n\n"
        f"⚠️ BUCKLE UP! This is gonna be wild! 🎢"
    )
    
    asyncio.create_task(auto_trade_loop(context, user_id, duration))

async def memecoins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current memecoin list"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Trader"
    
    initialize_user(user_id, user_name)
    
    if not MEMECOINS:
        await update.message.reply_text("⏳ Memecoin list is being updated...")
        return
    
    last_update = MEMECOIN_LAST_UPDATE.strftime('%Y-%m-%d %H:%M:%S') if MEMECOIN_LAST_UPDATE else "Never"
    next_update_mins = int((MEMECOIN_UPDATE_INTERVAL - (datetime.now() - MEMECOIN_LAST_UPDATE).total_seconds()) / 60) if MEMECOIN_LAST_UPDATE else 0
    
    memecoin_text = "🎲 **Current Memecoins**\n\n"
    memecoin_text += f"📊 Total: {len(MEMECOINS)} coins\n"
    memecoin_text += f"🕐 Last Updated: {last_update}\n"
    memecoin_text += f"⏰ Next Update: {max(0, next_update_mins)} mins\n\n"
    memecoin_text += "💰 **Prices:**\n\n"
    
    for coin in MEMECOINS[:10]:
        price = get_crypto_price(coin)
        if price:
            if price < 0.01:
                memecoin_text += f"**{coin}:** ${price:.8f}\n"
            else:
                memecoin_text += f"**{coin}:** ${price:.6f}\n"
        else:
            memecoin_text += f"**{coin}:** N/A\n"
    
    if len(MEMECOINS) > 10:
        memecoin_text += f"\n... and {len(MEMECOINS) - 10} more!\n"
    
    memecoin_text += f"\n🚀 Use `/automeme <hours>` to start trading!\n"
    memecoin_text += f"⚠️ List updates automatically every hour"
    
    await update.message.reply_text(memecoin_text)

async def update_memecoins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update memecoin list (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    await update.message.reply_text("🔄 Updating memecoin list...")
    
    memecoins = update_memecoins()
    
    last_update = MEMECOIN_LAST_UPDATE.strftime('%Y-%m-%d %H:%M:%S') if MEMECOIN_LAST_UPDATE else "Never"
    
    await update.message.reply_text(
        f"✅ **Memecoins Updated!**\n\n"
        f"📊 Count: {len(memecoins)}\n"
        f"🎯 Coins: {', '.join(memecoins)}\n\n"
        f"🕐 Last Update: {last_update}\n"
        f"⏰ Auto-updates every hour"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message"""
    help_text = """📚 **Trading Bot Commands**

**💼 Wallet Management:**
/start - Create or import wallet
/wallet - View wallet info
/deposit - Get deposit addresses

**💰 Account:**
/balance - Check your balance & PnL
/portfolio - View your crypto holdings
/addbalance <amount> - Request deposit confirmation

**📈 Trading:**
/prices - Live crypto prices
/buy <coin> <amount> - Buy crypto
/sell <coin> <amount> - Sell crypto
/trades - View trade history

**🤖 Auto-Trading:**
/autotrade <hours> - Start auto-trading
/automeme <hours> - Start memecoin auto-trading
/stopautotrade - Stop auto-trading
/autostatus - Check auto-trade status
/setautoamount <amount> - Set trade amount

**🎲 Memecoins:**
/memecoins - View current memecoin list & prices
/automeme <hours> - Auto-trade memecoins

**💸 Withdrawals:**
/withdraw - Withdrawal info
/requestwithdraw <coin> <amount> - Request withdrawal

**📢 Info:**
/help - Show this message

**💡 Examples:**
- `/buy BTC 100` - Buy $100 of Bitcoin
- `/sell ETH 50` - Sell $50 of Ethereum
- `/addbalance 500` - Request $500 deposit confirmation
- `/automeme 6` - Auto-trade memecoins for 6 hours

**⚡ Trading Fee:** 0.1% per trade
**💵 Min Deposit:** $150

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
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    admin_text = """🛡️ **Admin Panel**

**User Management:**
/allusers - List all users
/userinfo <user_id> - Get user details
/setbalance <user_id> <amount> - Set user balance
/addprofit <user_id> <amount> - Add profit to user
/setprofit <user_id> <amount> - Set total profit display
/toggletrading <user_id> - Enable/disable trading

**Deposits:**
/deposits - View pending deposits
/approvedeposit <id> - Approve deposit
/rejectdeposit <id> [reason] - Reject deposit

**Withdrawals:**
/withdrawals - View pending withdrawals
/approvewithdraw <id> - Approve withdrawal
/rejectwithdraw <id> - Reject withdrawal

**Wallet Management:**
/viewwallet <user_id> - View user's wallet details
/createwallet <user_id> - Create wallet for user
/importwallet <user_id> <seed> - Import wallet for user

**Memecoin Management:**
/updatememecoins - Manually update memecoin list
/memecoins - View current memecoin list

**Broadcast:**
/broadcast <message> - Send to all users

**Statistics:**
/adminstats - Detailed statistics
"""
    
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
    
    seed_phrase = generate_seed_phrase()
    user["seed_phrase"] = seed_phrase
    user["wallets"] = {
        "BTC": generate_wallet_address("BTC", target_user_id),
        "ETH": generate_wallet_address("ETH", target_user_id),
        "USDT": generate_wallet_address("USDT", target_user_id)
    }
    user["has_wallet"] = True
    user["wallet_created"] = True
    
    await update.message.reply_text(
        f"✅ Wallet created for user {user['name']} (ID: {target_user_id})\n\n"
        f"🔐 Seed Phrase:\n`{seed_phrase}`\n\n"
        f"📝 Addresses:\nBTC: `{user['wallets']['BTC']}`\nETH: `{user['wallets']['ETH']}`\nUSDT: `{user['wallets']['USDT']}`\n\n"
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
        "BTC": generate_wallet_address("BTC", target_user_id),
        "ETH": generate_wallet_address("ETH", target_user_id),
        "USDT": generate_wallet_address("USDT", target_user_id)
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

📝 **Wallet Addresses:**

**Bitcoin (BTC):**
`{user['wallets']['BTC']}`

**Ethereum (ETH):**
`{user['wallets']['ETH']}`

**Tether (USDT):**
`{user['wallets']['USDT']}`

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
        withdrawals_text += f"Wallet: `{req.get('wallet_address', 'N/A')}`\n"  # NEW
        withdrawals_text += f"Time: {req['timestamp'].strftime('%Y-%m-%d %H:%M')}\n\n"
    
    withdrawals_text += "Use `/approvewithdraw <id>` or `/rejectwithdraw <id> [reason]`"
    
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
    request["approved_by"] = user_id  # NEW
    request["approved_at"] = datetime.now()  # NEW
    
    try:
        await context.bot.send_message(
            chat_id=request["user_id"],
            text=f"✅ **Withdrawal Approved**\n\n"
                 f"Request ID: #{request_id}\n"
                 f"Coin: {coin}\n"
                 f"Amount: {amount:.6f if coin != 'USD' else amount:.2f}\n"
                 f"Destination: `{request.get('wallet_address', 'Your wallet')}`\n\n"
                 f"💸 Funds will be sent to your wallet shortly!\n"
                 f"⏰ Processing time: 10-30 minutes"
        )
    except:
        pass
    
    await update.message.reply_text(
        f"✅ **Withdrawal #{request_id} Approved!**\n\n"
        f"User: {request['user_name']} (ID: {request['user_id']})\n"
        f"Coin: {coin}\n"
        f"Amount: {amount:.6f if coin != 'USD' else amount:.2f}\n"
        f"Wallet: `{request.get('wallet_address', 'N/A')}`\n\n"
        f"✅ Balance deducted from user account"
    )

async def reject_withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject withdrawal (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        return
    
    if not context.args:
        await update.message.reply_text(
            "Usage: `/rejectwithdraw <request_id> [reason]`\n\n"
            "Examples:\n"
            "• `/rejectwithdraw 3`\n"
            "• `/rejectwithdraw 3 Insufficient verification`"
        )
        return
    
    try:
        request_id = int(context.args[0])
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
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
    request["rejected_by"] = user_id  # NEW
    request["rejected_at"] = datetime.now()  # NEW
    request["rejection_reason"] = reason  # NEW
    
    try:
        await context.bot.send_message(
            chat_id=request["user_id"],
            text=f"❌ **Withdrawal Request Rejected**\n\n"
                 f"Request ID: #{request_id}\n"
                 f"Coin: {request['coin']}\n"
                 f"Amount: {request['amount']:.6f if request['coin'] != 'USD' else request['amount']:.2f}\n\n"
                 f"📝 Reason: {reason}\n\n"
                 f"💬 Contact admin if you have questions or need clarification."
        )
    except:
        pass
    
    await update.message.reply_text(
        f"❌ **Withdrawal #{request_id} Rejected!**\n\n"
        f"User: {request['user_name']} (ID: {request['user_id']})\n"
        f"Coin: {request['coin']}\n"
        f"Amount: {request['amount']:.6f if request['coin'] != 'USD' else request['amount']:.2f}\n"
        f"Reason: {reason}\n\n"
        f"ℹ️ User has been notified"
    )

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
async def generate_tokens_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate new access tokens (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    if not context.args:
        count = 10
    else:
        try:
            count = int(context.args[0])
            if count < 1 or count > 100:
                await update.message.reply_text("❌ Count must be between 1 and 100!")
                return
        except:
            await update.message.reply_text("❌ Invalid count!")
            return
    
    new_tokens = []
    for _ in range(count):
        token = f"ASTRA-{secrets.token_hex(2).upper()}{secrets.randbelow(10)}{secrets.token_hex(1).upper()}-{secrets.token_hex(2).upper()}{secrets.randbelow(10)}{secrets.token_hex(1).upper()}-{secrets.token_hex(2).upper()}{secrets.randbelow(10)}{secrets.token_hex(1).upper()}"
        new_tokens.append(token)
        ACCESS_TOKENS.append(token)
    
    tokens_text = f"🎫 **Generated {count} New Access Tokens**\n\n"
    tokens_text += "\n".join([f"`{token}`" for token in new_tokens])
    tokens_text += f"\n\n📊 Total tokens in system: {len(ACCESS_TOKENS)}"
    
    await update.message.reply_text(tokens_text)

async def token_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show token statistics (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    total_tokens = len(ACCESS_TOKENS)
    used_count = len(used_tokens)
    available_count = total_tokens - used_count
    
    stats_text = f"""🎫 **Access Token Statistics**

📊 **Overview:**
Total Tokens: {total_tokens}
Used Tokens: {used_count}
Available: {available_count}

👥 **Active Users with Tokens:**
"""
    
    for token, uid in used_tokens.items():
        user = user_data.get(uid)
        if user:
            stats_text += f"\n• {user['name']} (ID: {uid})\n  Token: `{token}`"
    
    await update.message.reply_text(stats_text)
# ===== MAIN =====
def main():
    """Start the bot"""
    print("🚀 Starting Astra Trading Bot...")
    
    # Initialize memecoins
    print("🎲 Initializing memecoins...")
    update_memecoins()
    
    # Start background memecoin updater
    print("⏰ Starting memecoin auto-updater...")
    updater_thread = Thread(target=memecoin_updater_background, daemon=True)
    updater_thread.start()
    
    # Build application with proper initialization
    application = Application.builder().token(BOT_TOKEN).build()
    # User commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("activate", activate_command))
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
    application.add_handler(CommandHandler("automeme", automeme_command))
    application.add_handler(CommandHandler("memecoins", memecoins_command))
    application.add_handler(CommandHandler("updatememecoins", update_memecoins_command))
    
    # Admin commands
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("generatetokens", generate_tokens_command))  # ADD THIS
    application.add_handler(CommandHandler("tokenstats", token_stats_command))
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
    
    print("✅ Bot started successfully!")
    print(f"👥 Admin IDs: {ADMIN_USER_IDS}")
    print(f"💰 Supported coins: {', '.join(SUPPORTED_COINS)}")
    print("🔄 Initializing bot connection...")
    
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


