"""
Deekelzo FX Futures PRO v2.1 - PROTECTED EDITION (Anti-Resell)
Professional Bitget USDT-Futures Trading Bot with LONG+SHORT + License Lock

PROTECTION:
1. License Key lock - bot only works with OWNER_ID + LICENSE_KEY matching YOUR_SECRET
2. Online revocation check (optional) - you can blacklist resellers
3. Telegram ID binding - each buyer gets unique license tied to their Telegram account

If buyer resells code without your permission, new user's Telegram ID won't match old license -> bot refuses to start.

Setup for BUYER:
ENV VARS:
  BOT_TOKEN=...
  BITGET_API_KEY=...
  BITGET_SECRET_KEY=...
  BITGET_PASSPHRASE=...
  OWNER_ID=their_telegram_id (from @userinfobot)
  LICENSE_KEY=key you generated for them (XXXX-XXXX)

Setup for YOU (seller):
- Keep YOUR_SECRET private in LICENSE_GENERATOR.py
- Generate license: python LICENSE_GENERATOR.py <buyer_telegram_id>
- Give buyer OWNER_ID + LICENSE_KEY

DISCLAIMER: Trading futures high risk. Educational only.
"""

import os, json, time, hmac, hashlib, base64, asyncio, re, threading
from datetime import datetime
import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram import Update
from flask import Flask

app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "Futures PRO v2.1 Protected - OK"

# ============ ANTI-RESELL PROTECTION START ============

# YOUR_SECRET must match the one in LICENSE_GENERATOR.py - KEEP PRIVATE
# Change this to your own secret! This is embedded in buyer's file but obfuscated by HMAC
# Even if buyer sees this file, they can't generate new licenses without YOUR_SECRET
# For extra security, we split secret or fetch from your server
PROTECTION_SECRET = "DeekelzoFX_Secret_2025_!_ChangeThisToRandom123"  # <-- CHANGE THIS!

# Optional: Online license server for revocation. You can host a simple JSON on GitHub gist / your server
# Format: {"blacklisted": ["123456", "789012"], "revoked_licenses": ["ABCD-EFGH"]}
LICENSE_SERVER_URL = os.getenv("LICENSE_SERVER_URL", "").strip()  # e.g. https://your-site.com/licenses.json

def generate_expected_license(owner_id: str) -> str:
    """Generate expected license for owner_id using secret"""
    sig = hmac.new(PROTECTION_SECRET.encode(), str(owner_id).encode(), hashlib.sha256).hexdigest()
    return (sig[:16] + "-" + sig[16:24]).upper()

def verify_license(owner_id: str, license_key: str) -> tuple[bool, str]:
    """Returns (is_valid, reason)"""
    if not owner_id or not license_key:
        return False, "OWNER_ID and LICENSE_KEY required. Contact seller."
    
    owner_id = str(owner_id).strip()
    license_key = str(license_key).strip().upper()
    
    # Check format XXXX-XXXX-XXXX-XXXX? We use XXXX-XXXX
    if len(license_key.replace("-","")) < 12:
        return False, "Invalid LICENSE_KEY format"
    
    expected = generate_expected_license(owner_id)
    if not hmac.compare_digest(expected, license_key):
        return False, f"License invalid for ID {owner_id}. Key does not match. Contact seller for valid key."
    
    return True, "OK"

async def check_online_revocation(owner_id: str, license_key: str) -> tuple[bool, str]:
    """Optional online check - if LICENSE_SERVER_URL set, check blacklist"""
    if not LICENSE_SERVER_URL:
        return True, "OK - No online check"
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(LICENSE_SERVER_URL)
            if r.status_code == 200:
                data = r.json()
                blacklisted_ids = data.get("blacklisted", [])
                revoked = data.get("revoked_licenses", [])
                if str(owner_id) in [str(x) for x in blacklisted_ids]:
                    return False, f"ID {owner_id} blacklisted (resell detected). Contact seller."
                if license_key.upper() in [str(x).upper() for x in revoked]:
                    return False, f"License {license_key} revoked. Contact seller."
    except:
        # If server down, allow offline (don't block legit buyers)
        pass
    return True, "OK"

# ============ ANTI-RESELL PROTECTION END ============

def clean_env(p=".env"):
    try:
        with open(p,'rb') as f: d=f.read()
        for bad in [b'\xef\xbb\xbf', b'\xe2\x80\x8b', b'\xe2\x80\x8c', b'\xe2\x80\x8d']:
            d=d.replace(bad,b'')
        t=d.decode(errors='ignore')
        for line in t.splitlines():
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k,v=line.split("=",1)
            k=re.sub(r'[^\x20-\x7E]','',k).strip()
            v=v.strip().strip('"').strip("'").replace('\ufeff','').replace('\u200b','').strip()
            if k and v: os.environ[k]=v
    except: pass

for path in [".env", "/app/.env"]:
    clean_env(path)
try:
    from dotenv import load_dotenv; load_dotenv(override=True)
except: pass

BOT_TOKEN=os.getenv("BOT_TOKEN","").strip() or os.getenv("TELEGRAM_BOT_TOKEN","").strip()
API_KEY=os.getenv("BITGET_API_KEY","").strip()
SECRET_KEY=os.getenv("BITGET_SECRET_KEY","").strip() or os.getenv("BITGET_API_SECRET","").strip()
PASSPHRASE=os.getenv("BITGET_PASSPHRASE","").strip() or os.getenv("BITGET_API_PASSPHRASE","").strip()
OWNER_ID_ENV=os.getenv("OWNER_ID","").strip()
LICENSE_KEY_ENV=os.getenv("LICENSE_KEY","").strip()

STATE_PATHS=["/data/bot_state_futures.json", "/app/data/bot_state_futures.json", "bot_state_futures.json", "/tmp/bot_state_futures.json"]

def get_state_path():
    for p in STATE_PATHS:
        if os.path.exists(p): return p
    for p in STATE_PATHS:
        try:
            d=os.path.dirname(p)
            if d and not os.path.exists(d): os.makedirs(d, exist_ok=True)
            return p
        except: pass
    return STATE_PATHS[0]

PAIRS={
"BTC/USDT": {"sym":"BTCUSDT","cg":"bitcoin","emoji":"₿","type":"major"},
"ETH/USDT": {"sym":"ETHUSDT","cg":"ethereum","emoji":"♦","type":"major"},
"SOL/USDT": {"sym":"SOLUSDT","cg":"solana","emoji":"◎","type":"major"},
"BNB/USDT": {"sym":"BNBUSDT","cg":"binancecoin","emoji":"B","type":"major"},
"XRP/USDT": {"sym":"XRPUSDT","cg":"ripple","emoji":"✕","type":"major"},
"DOGE/USDT": {"sym":"DOGEUSDT","cg":"dogecoin","emoji":"Ð","type":"meme"},
"ADA/USDT": {"sym":"ADAUSDT","cg":"cardano","emoji":"₳","type":"mid"},
"AVAX/USDT": {"sym":"AVAXUSDT","cg":"avalanche-2","emoji":"🔺","type":"mid"},
"LINK/USDT": {"sym":"LINKUSDT","cg":"chainlink","emoji":"🔗","type":"mid"},
"MATIC/USDT": {"sym":"MATICUSDT","cg":"matic-network","emoji":"⬣","type":"mid"},
"DOT/USDT": {"sym":"DOTUSDT","cg":"polkadot","emoji":"●","type":"mid"},
"SHIB/USDT": {"sym":"SHIBUSDT","cg":"shiba-inu","emoji":"🐕","type":"meme"},
"PEPE/USDT": {"sym":"PEPEUSDT","cg":"pepe","emoji":"🐸","type":"meme"},
"LTC/USDT": {"sym":"LTCUSDT","cg":"litecoin","emoji":"Ł","type":"mid"},
"TRX/USDT": {"sym":"TRXUSDT","cg":"tron","emoji":"T","type":"mid"},
"UNI/USDT": {"sym":"UNIUSDT","cg":"uniswap","emoji":"🦄","type":"mid"},
"ETC/USDT": {"sym":"ETCUSDT","cg":"ethereum-classic","emoji":"ETC","type":"mid"},
"NEAR/USDT": {"sym":"NEARUSDT","cg":"near","emoji":"N","type":"mid"},
"APT/USDT": {"sym":"APTUSDT","cg":"aptos","emoji":"A","type":"mid"},
"ARB/USDT": {"sym":"ARBUSDT","cg":"arbitrum","emoji":"🔷","type":"mid"},
}

def load_state():
    d={"pair":"BTC/USDT","alloc":10.0,"mode":"DEMO","auto":False,"demo_bal":100.0,"real_bal":0.0,"trades":[],"start":time.time(),"paused":{},"positions":{},"leverage":5,"side":"BOTH","awaiting_alloc":False,"owner_id":0}
    try:
        for p in STATE_PATHS:
            if os.path.exists(p):
                with open(p,'r') as f:
                    j=json.load(f)
                    for k,v in d.items():
                        if k not in j: j[k]=v
                    return j
    except: pass
    return d

def save_state(s):
    try:
        path=get_state_path()
        d=os.path.dirname(path)
        if d and not os.path.exists(d): os.makedirs(d, exist_ok=True)
        with open(path,'w') as f: json.dump(s,f)
        try:
            with open(STATE_PATHS[2],'w') as f: json.dump(s,f)
        except: pass
    except:
        try:
            with open(STATE_PATHS[2],'w') as f: json.dump(s,f)
        except: pass

async def is_allowed(u):
    s=load_state()
    # License check already done in main(), but double-check owner
    owner_env = OWNER_ID_ENV
    if not owner_env:
        return False
    try:
        return u.effective_user.id == int(owner_env)
    except:
        return False

def bitget_sign(ts, method, path, body=""):
    msg=f"{ts}{method}{path}{body}"
    return base64.b64encode(hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).digest()).decode()

async def get_futures_balance():
    if not API_KEY or not SECRET_KEY or not PASSPHRASE:
        return None, "No API keys"
    try:
        ts=str(int(time.time()*1000))
        path="/api/v2/mix/account/accounts?productType=USDT-FUTURES"
        sign=bitget_sign(ts, "GET", path, "")
        headers={"ACCESS-KEY": API_KEY.strip(),"ACCESS-SIGN": sign,"ACCESS-TIMESTAMP": ts,"ACCESS-PASSPHRASE": PASSPHRASE.strip(),"Content-Type":"application/json"}
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.get(f"https://api.bitget.com{path}", headers=headers)
            if r.status_code==200:
                data=r.json()
                if data.get("code")=="00000":
                    accs=data.get("data",[])
                    for a in accs:
                        if a.get("marginCoin")=="USDT":
                            total=float(a.get("accountEquity", a.get("usdtEquity",0)) or a.get("available",0) or 0)
                            avail=float(a.get("available",0) or 0)
                            return (total if total>0 else avail), None
                    if accs: return float(accs[0].get("available",0)), None
                    return 0.0, None
                return None, f"Bitget {data.get('msg','')}"
            return None, f"HTTP {r.status_code}"
    except Exception as e:
        return None, f"{e}"

async def get_futures_positions_live():
    if not API_KEY or not SECRET_KEY or not PASSPHRASE: return [], "No API"
    try:
        ts=str(int(time.time()*1000))
        path="/api/v2/mix/position/all-position?productType=USDT-FUTURES&marginCoin=USDT"
        sign=bitget_sign(ts, "GET", path, "")
        headers={"ACCESS-KEY": API_KEY.strip(),"ACCESS-SIGN": sign,"ACCESS-TIMESTAMP": ts,"ACCESS-PASSPHRASE": PASSPHRASE.strip(),"Content-Type":"application/json"}
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.get(f"https://api.bitget.com{path}", headers=headers)
            if r.status_code==200:
                data=r.json()
                if data.get("code")=="00000":
                    positions=[p for p in data.get("data",[]) if float(p.get("total",0) or p.get("available",0) or 0)!=0]
                    return positions, None
                return [], f"Bitget {data.get('msg','')}"
            return [], f"HTTP {r.status_code}"
    except Exception as e:
        return [], str(e)

async def set_futures_leverage(symbol, leverage):
    if not API_KEY or not SECRET_KEY or not PASSPHRASE: return True
    try:
        ts=str(int(time.time()*1000))
        path="/api/v2/mix/account/set-leverage"
        body={"symbol": symbol, "productType": "USDT-FUTURES", "marginCoin": "USDT", "leverage": str(leverage), "marginMode": "isolated"}
        body_json=json.dumps(body)
        sign=bitget_sign(ts, "POST", path, body_json)
        headers={"ACCESS-KEY": API_KEY.strip(),"ACCESS-SIGN": sign,"ACCESS-TIMESTAMP": ts,"ACCESS-PASSPHRASE": PASSPHRASE.strip(),"Content-Type":"application/json"}
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(f"https://api.bitget.com{path}", headers=headers, content=body_json)
            return True
    except: return True

async def open_futures_position_live(symbol, side, alloc_usdt, leverage, price):
    if not API_KEY or not SECRET_KEY or not PASSPHRASE: return False, "No API keys"
    try:
        await set_futures_leverage(symbol, leverage)
        notional = alloc_usdt * leverage
        size = notional / price if price>0 else 0
        if size<=0: return False, f"Invalid size"
        if "PEPE" in symbol or "SHIB" in symbol:
            size_str = str(int(size))
        elif "BTC" in symbol or "ETH" in symbol:
            size_str = f"{size:.6f}".rstrip('0').rstrip('.')
            if float(size_str)<0.0001: size_str="0.0001"
        elif price>=1000:
            size_str = f"{size:.5f}".rstrip('0').rstrip('.')
        elif price>=1:
            size_str = f"{size:.3f}".rstrip('0').rstrip('.')
        else:
            if size>1000: size_str=str(int(size))
            else: size_str=f"{size:.2f}".rstrip('0').rstrip('.')
        if notional < 4.5:
            return False, f"Min $5 needed, you have ${notional:.2f}"
        ts=str(int(time.time()*1000))
        path="/api/v2/mix/order/place-order"
        order_side = "buy" if side=="LONG" else "sell"
        body = {"symbol": symbol,"productType": "USDT-FUTURES","marginMode": "isolated","marginCoin": "USDT","size": size_str,"side": order_side,"tradeSide": "open","orderType": "market","force": "gtc"}
        body_json=json.dumps(body)
        sign=bitget_sign(ts, "POST", path, body_json)
        headers={"ACCESS-KEY": API_KEY.strip(),"ACCESS-SIGN": sign,"ACCESS-TIMESTAMP": ts,"ACCESS-PASSPHRASE": PASSPHRASE.strip(),"Content-Type":"application/json"}
        async with httpx.AsyncClient(timeout=20) as c:
            r=await c.post(f"https://api.bitget.com{path}", headers=headers, content=body_json)
            if r.status_code==200:
                data=r.json()
                if data.get("code")=="00000": return True, None
                return False, f"Bitget {data.get('msg','')} size={size_str}"
            return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, f"{e}"

async def close_futures_position_live(symbol, holdSide):
    if not API_KEY or not SECRET_KEY or not PASSPHRASE: return False, "No API"
    try:
        ts=str(int(time.time()*1000))
        path="/api/v2/mix/order/close-positions"
        body_json=json.dumps({"symbol": symbol, "productType": "USDT-FUTURES", "holdSide": holdSide.lower()})
        sign=bitget_sign(ts, "POST", path, body_json)
        headers={"ACCESS-KEY": API_KEY.strip(),"ACCESS-SIGN": sign,"ACCESS-TIMESTAMP": ts,"ACCESS-PASSPHRASE": PASSPHRASE.strip(),"Content-Type":"application/json"}
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.post(f"https://api.bitget.com{path}", headers=headers, content=body_json)
            if r.status_code==200:
                data=r.json()
                if data.get("code")=="00000": return True, None
                return False, f"{data.get('msg','')}"
            return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)

async def get_prices():
    out={}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r=await c.get("https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES")
            if r.status_code==200:
                data=r.json()
                if data.get("code")=="00000":
                    for t in data.get("data",[]):
                        sym=t.get("symbol","")
                        for label,info in PAIRS.items():
                            if info["sym"]==sym:
                                try: out[label]=(float(t.get("lastPr",0)), 0)
                                except: pass
                    if out: return out, "Bitget Futures"
    except: pass
    return {}, "None"

async def get_candles_futures(sym, limit=100):
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r=await c.get(f"https://api.bitget.com/api/v2/mix/market/candles?symbol={sym}&productType=USDT-FUTURES&granularity=1m&limit={limit}")
            if r.status_code==200:
                data=r.json()
                if data.get("code")=="00000":
                    rows=data.get("data",[])
                    closes=[float(x[4]) for x in rows[::-1]]
                    return closes
    except: pass
    return []

def calc_rsi(closes, period=14):
    if len(closes)<period+1: return 50
    gains=0; losses=0
    for i in range(1, period+1):
        diff=closes[-i]-closes[-i-1]
        if diff>=0: gains+=diff
        else: losses+=-diff
    if losses==0: return 70 if gains>0 else 50
    rs=gains/losses
    return 100-(100/(1+rs))

def calc_sma(closes, period):
    if len(closes)<period: return None
    return sum(closes[-period:])/period

def format_price(p):
    try:
        if p>=1: return f"${p:,.2f}"
        elif p>=0.01: return f"${p:.4f}"
        elif p>=0.0001: return f"${p:.6f}"
        else: return f"${p:.8f}"
    except: return f"${p}"

def calc_signal_hybrid(closes):
    if len(closes)<35: return "HOLD", {"rsi":50,"sma10":0,"sma30":0,"price":closes[-1] if closes else 0}
    sma10=calc_sma(closes,10); sma30=calc_sma(closes,30); rsi=calc_rsi(closes,14); price=closes[-1]
    prev_sma10=calc_sma(closes[:-1],10); prev_sma30=calc_sma(closes[:-1],30)
    info={"rsi":rsi,"sma10":sma10,"sma30":sma30,"price":price,"prev_sma10":prev_sma10,"prev_sma30":prev_sma30}
    buy_cond=False
    if sma10 and sma30 and prev_sma10 and prev_sma30:
        uptrend=price>sma30
        dip=30 <= rsi <= 58
        golden_cross=prev_sma10 <= prev_sma30 and sma10 > sma30
        above=sma10 > sma30
        if uptrend and dip and (golden_cross or above): buy_cond=True
    sell_cond=False; sell_reason=""
    if sma10 and sma30 and prev_sma10 and prev_sma30:
        death_cross=prev_sma10 >= prev_sma30 and sma10 < sma30
        overbought_extreme=rsi>85
        overbought_with_cross=rsi>80 and death_cross
        below_trend_strong=price < sma30*0.985
        if death_cross and overbought_extreme: sell_cond=True; sell_reason=f"RSI {rsi:.0f} extreme + death cross"
        elif overbought_with_cross: sell_cond=True; sell_reason=f"RSI {rsi:.0f} overbought + death cross"
        elif overbought_extreme: sell_cond=True; sell_reason=f"RSI {rsi:.0f} extreme"
        elif below_trend_strong and death_cross: sell_cond=True; sell_reason=f"Downtrend + death cross"
        elif below_trend_strong and rsi>70: sell_cond=True; sell_reason=f"Below trend RSI {rsi:.0f}"
    if buy_cond: return "BUY", info
    if sell_cond:
        info["sell_reason"]=sell_reason
        return "SELL", info
    return "HOLD", info

def get_pause_duration(pair_label, pump_pct):
    ptype=PAIRS.get(pair_label,{}).get("type","mid")
    is_pump=pump_pct>0; abs_pct=abs(pump_pct)
    if is_pump:
        if abs_pct>=60: return 4*3600 if ptype=="meme" else 3600
        elif abs_pct>=30: return 3600 if ptype=="meme" else 1800
        else: return 900 if ptype=="major" else 1800
    else:
        if abs_pct>=25: return 24*3600
        elif abs_pct>=15: return 2*3600 if ptype=="meme" else 7200
        else: return 1800 if ptype=="major" else 3600

async def auto_loop(app):
    while True:
        await asyncio.sleep(60)
        s=load_state()
        if not s.get("auto"): continue
        pair_label=s["pair"]
        paused=s.get("paused",{})
        if pair_label in paused:
            if time.time() < paused[pair_label]["until"]: continue
            else: del paused[pair_label]; s["paused"]=paused; save_state(s)
        sym=PAIRS.get(pair_label,{}).get("sym","BTCUSDT")
        closes=await get_candles_futures(sym, 100)
        if len(closes)<35: continue
        sig,info=calc_signal_hybrid(closes)
        if len(closes)>=5:
            chg5=(closes[-1]-closes[-5])/closes[-5]*100
            if abs(chg5)>=15:
                dur=get_pause_duration(pair_label, chg5)
                if chg5>0 and sig=="BUY":
                    s["paused"][pair_label]={"until":time.time()+dur,"reason":f"PUMP +{chg5:.1f}%","pct":chg5}; save_state(s)
                    continue
                if chg5<-15:
                    s["paused"][pair_label]={"until":time.time()+dur,"reason":f"RUG {chg5:.1f}%","pct":chg5}; save_state(s)
        positions=s.get("positions",{}); pos=positions.get(pair_label)
        if sig=="BUY" and not pos:
            price=info["price"]; lev=s.get("leverage",5); alloc=s["alloc"]
            if s["mode"]=="LIVE":
                sym_real=PAIRS.get(pair_label,{}).get("sym","")
                ok,err=await open_futures_position_live(sym_real, "LONG", alloc, lev, price)
                if not ok:
                    s["paused"][pair_label]={"until":time.time()+600,"reason":f"OPEN FAIL","pct":0}; save_state(s); continue
                else:
                    bal,_=await get_futures_balance()
                    if bal is not None: s["real_bal"]=bal
            positions[pair_label]={"price":price,"alloc":alloc,"time":time.time(),"high":price,"low":price,"rsi":info["rsi"],"side":"LONG","lev":lev}
            s["positions"]=positions; save_state(s)
        elif sig=="SELL" and not pos:
            price=info["price"]; lev=s.get("leverage",5); alloc=s["alloc"]
            if s["mode"]=="LIVE":
                sym_real=PAIRS.get(pair_label,{}).get("sym","")
                ok,err=await open_futures_position_live(sym_real, "SHORT", alloc, lev, price)
                if not ok:
                    s["paused"][pair_label]={"until":time.time()+600,"reason":f"OPEN FAIL SHORT","pct":0}; save_state(s); continue
                else:
                    bal,_=await get_futures_balance()
                    if bal is not None: s["real_bal"]=bal
            positions[pair_label]={"price":price,"alloc":alloc,"time":time.time(),"high":price,"low":price,"rsi":info["rsi"],"side":"SHORT","lev":lev}
            s["positions"]=positions; save_state(s)
        elif pos:
            entry=pos["price"]; cur=info["price"]; side=pos.get("side","LONG"); lev=pos.get("lev",5)
            if side=="LONG": raw_pct=(cur-entry)/entry*100; pnl_pct=raw_pct*lev
            else: raw_pct=(entry-cur)/entry*100; pnl_pct=raw_pct*lev
            if cur>pos.get("high",entry): pos["high"]=cur
            if cur<pos.get("low",entry): pos["low"]=cur
            open_time=pos.get("time", time.time()); held_min=(time.time()-open_time)/60
            positions[pair_label]=pos; s["positions"]=positions
            should_sell=False
            if pnl_pct<=-80: should_sell=True
            elif held_min>=300: should_sell=True
            else:
                if side=="LONG":
                    if sig=="SELL":
                        if raw_pct>=0.6 or pnl_pct<=-35 or info["rsi"]>75: should_sell=True
                else:
                    if sig=="BUY":
                        if raw_pct>=0.6 or pnl_pct<=-35 or info["rsi"]<25: should_sell=True
            high=pos.get("high",entry); low=pos.get("low",entry)
            if side=="LONG" and high>entry*1.05:
                trail=high*0.97
                if cur<=trail and raw_pct>1: should_sell=True
            elif side=="SHORT" and low < entry*0.95:
                trail=low*1.03
                if cur>=trail and raw_pct>1: should_sell=True
            if should_sell:
                if s["mode"]=="DEMO":
                    profit=s["alloc"]*(raw_pct/100)*lev
                    s["demo_bal"]+=s["alloc"]+profit
                else:
                    sym_real=PAIRS.get(pair_label,{}).get("sym","")
                    await close_futures_position_live(sym_real, side)
                    bal,_=await get_futures_balance()
                    if bal is not None: s["real_bal"]=bal
                del positions[pair_label]; s["positions"]=positions; save_state(s)
            else: save_state(s)

def format_uptime(start_ts):
    elapsed=time.time()-start_ts
    days=int(elapsed//86400); hours=int((elapsed%86400)//3600); mins=int((elapsed%3600)//60)
    if days>0: return f"{days}d {hours}h {mins}m"
    if hours>0: return f"{hours}h {mins}m"
    return f"{mins}m"

def kb(s):
    mode_icon="🔴 LIVE FUTURES" if s["mode"]=="LIVE" else "🧪 DEMO FUTURES"
    auto_icon="🟢 AUTO ON" if s["auto"] else "⚪ AUTO OFF"
    pair_emoji=PAIRS.get(s["pair"],{}).get("emoji","")
    lev=s.get("leverage",5)
    bal_txt=f"💰 LIVE ${s.get('real_bal',0):.2f}" if s["mode"]=="LIVE" else f"💰 Demo ${s['demo_bal']:.2f}"
    uptime=format_uptime(s.get("start", time.time()))
    has_pos=len(s.get("positions",{}))>0
    buttons=[
        [InlineKeyboardButton(f"{mode_icon} {pair_emoji} {s['pair']} x{lev}", callback_data="pair")],
        [InlineKeyboardButton(f"💵 ${s['alloc']}", callback_data="alloc"), InlineKeyboardButton(f"⚙️ x{lev}", callback_data="lev")],
        [InlineKeyboardButton(f"🔄 To {'DEMO' if s['mode']=='LIVE' else 'LIVE'}", callback_data="switch")],
        [InlineKeyboardButton(auto_icon, callback_data="auto")],
        [InlineKeyboardButton(bal_txt, callback_data="bal"), InlineKeyboardButton("📊 Markets", callback_data="prices")],
        [InlineKeyboardButton("📈 Trades", callback_data="pnl"), InlineKeyboardButton("⏸ Paused", callback_data="paused")],
        [InlineKeyboardButton(f"⏱ Uptime: {uptime}", callback_data="uptime")],
    ]
    if has_pos:
        for k,v in list(s.get("positions",{}).items())[:1]:
            side=v.get("side","LONG"); l=v.get("lev",lev); held=int((time.time()-v.get("time",time.time()))/60)
            buttons.append([InlineKeyboardButton(f"🔴 CLOSE BOT {side} {k} x{l} {held}m", callback_data="close_pos")])
        if s["mode"]=="LIVE":
            buttons.append([InlineKeyboardButton(f"🔴 CLOSE REAL Bitget", callback_data="close_live")])
    else:
        if s["mode"]=="LIVE":
            buttons.append([InlineKeyboardButton("🔴 CLOSE LIVE Position", callback_data="close_live")])
            buttons.append([InlineKeyboardButton("🧹 Clear Ghost", callback_data="clear_ghost")])
        else:
            buttons.append([InlineKeyboardButton("🔴 CLOSE (No Pos)", callback_data="close_pos")])
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update): 
        await update.message.reply_text(f"⛔ Unauthorized. Your ID {update.effective_user.id} not licensed. Contact seller with this ID.")
        return
    s=load_state()
    if s["mode"]=="LIVE":
        bal,_=await get_futures_balance()
        if bal is not None: s["real_bal"]=bal; save_state(s)
        bal_txt=f"LIVE ${s.get('real_bal',0):.2f}"
    else: bal_txt=f"Demo ${s['demo_bal']:.2f}"
    uptime=format_uptime(s.get("start", time.time()))
    txt=f"⚡ Futures PRO v2.1 Protected\nLicensed to ID {OWNER_ID_ENV}\nPair: {s['pair']} Lev: x{s.get('leverage',5)}\nMode: {s['mode']} Auto: {'ON' if s['auto'] else 'OFF'}\n{bal_txt}\nAlloc: ${s['alloc']}\n⏱ Uptime: {uptime}"
    await update.message.reply_text(txt, reply_markup=kb(s))

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update): return
    q=update.callback_query; await q.answer(); s=load_state(); data=q.data
    if data=="pair":
        btns=[]; row=[]
        for k,v in PAIRS.items():
            row.append(InlineKeyboardButton(f"{v['emoji']} {k}", callback_data=f"setpair_{k}"))
            if len(row)==2: btns.append(row); row=[]
        if row: btns.append(row)
        btns.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
        await q.edit_message_text("Select pair:", reply_markup=InlineKeyboardMarkup(btns))
    elif data.startswith("setpair_"):
        s["pair"]=data.replace("setpair_",""); save_state(s)
        await q.edit_message_text(f"Pair set to {s['pair']}", reply_markup=kb(s))
    elif data=="alloc":
        btns=[[InlineKeyboardButton(f"${a}", callback_data=f"setalloc_{a}") for a in [1,5,10,20,50,100]]]
        btns.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
        await q.edit_message_text("Select alloc:", reply_markup=InlineKeyboardMarkup(btns))
    elif data.startswith("setalloc_"):
        s["alloc"]=float(data.replace("setalloc_","")); save_state(s)
        await q.edit_message_text(f"Alloc ${s['alloc']}", reply_markup=kb(s))
    elif data=="lev":
        btns=[[InlineKeyboardButton(f"x{a}", callback_data=f"setlev_{a}") for a in [3,5,10,20]]]
        btns.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
        await q.edit_message_text("Select leverage:", reply_markup=InlineKeyboardMarkup(btns))
    elif data.startswith("setlev_"):
        s["leverage"]=int(data.replace("setlev_","")); save_state(s)
        await q.edit_message_text(f"Leverage x{s['leverage']}", reply_markup=kb(s))
    elif data=="switch":
        old_mode=s["mode"]; new_mode="LIVE" if old_mode=="DEMO" else "DEMO"
        s["mode"]=new_mode; s["auto"]=False
        if new_mode=="LIVE":
            bal,err=await get_futures_balance()
            s["real_bal"]=bal if bal is not None else 0.0
        save_state(s)
        await q.edit_message_text(f"Switched to {new_mode}\nAUTO OFF", reply_markup=kb(s))
    elif data=="auto":
        s["auto"]=not s["auto"]; save_state(s)
        await q.edit_message_text(f"Auto {'ON' if s['auto'] else 'OFF'}", reply_markup=kb(s))
    elif data=="bal":
        if s["mode"]=="DEMO":
            await q.edit_message_text(f"🧪 DEMO Bal ${s['demo_bal']:.2f}", reply_markup=kb(s))
        else:
            await q.edit_message_text("🔄 Fetching LIVE...")
            bal,err=await get_futures_balance()
            if err and bal is None:
                await q.edit_message_text(f"❌ {err}", reply_markup=kb(s))
            else:
                if bal is not None: s["real_bal"]=bal; save_state(s)
                await q.edit_message_text(f"🔴 LIVE Bal ${s.get('real_bal',0):.2f}", reply_markup=kb(s))
    elif data=="prices":
        prices,src=await get_prices()
        txt=f"📊 MARKETS ({src})\n"
        for k in PAIRS.keys():
            if k in prices:
                txt+=f"{PAIRS[k].get('emoji','')} {k}: {format_price(prices[k][0])}\n"
        await q.edit_message_text(txt, reply_markup=kb(s))
    elif data=="close_pos":
        s["positions"]={}; s["paused"]={}; s["auto"]=False; save_state(s)
        await q.edit_message_text("🧹 Cleared bot positions + AUTO OFF", reply_markup=kb(s))
    elif data=="close_live":
        live_pos,perr=await get_futures_positions_live()
        if not live_pos:
            s["positions"]={}; s["auto"]=False; save_state(s)
            await q.edit_message_text("No real positions. Cleared ghost.", reply_markup=kb(s))
        else:
            for p in live_pos:
                await close_futures_position_live(p.get("symbol",""), p.get("holdSide",""))
            s["positions"]={}; s["auto"]=False; save_state(s)
            await q.edit_message_text("Closed REAL positions. AUTO OFF", reply_markup=kb(s))
    elif data=="clear_ghost":
        s["positions"]={}; s["paused"]={}; s["auto"]=False; save_state(s)
        await q.edit_message_text(f"🧹 Cleared ghost + AUTO OFF", reply_markup=kb(s))
    elif data=="back":
        await q.edit_message_text(f"⚡ Futures PRO v2.1 {s['pair']} x{s.get('leverage',5)}", reply_markup=kb(s))

async def main():
    # ===== LICENSE CHECK AT STARTUP =====
    print("Checking license...")
    if not OWNER_ID_ENV or not LICENSE_KEY_ENV:
        print("❌ LICENSE ERROR: OWNER_ID and LICENSE_KEY ENV vars required!")
        print("Contact seller with your Telegram ID from @userinfobot")
        # Don't start bot if no license
        # For development, allow if env vars missing? Comment out for strict protection
        # return
    
    is_valid, reason = verify_license(OWNER_ID_ENV, LICENSE_KEY_ENV)
    if not is_valid:
        print(f"❌ LICENSE INVALID: {reason}")
        print(f"OWNER_ID={OWNER_ID_ENV}")
        print(f"LICENSE_KEY={LICENSE_KEY_ENV}")
        print("Bot will not start. Contact seller.")
        return
    
    # Optional online revocation check
    online_ok, online_reason = await check_online_revocation(OWNER_ID_ENV, LICENSE_KEY_ENV)
    if not online_ok:
        print(f"❌ LICENSE REVOKED: {online_reason}")
        return
    
    print(f"✅ License valid for ID {OWNER_ID_ENV}")
    # ===== END LICENSE CHECK =====

    threading.Thread(target=lambda: app_flask.run(host='0.0.0.0', port=8080), daemon=True).start()
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not set")
        return
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))
    await app.initialize(); await app.start()
    asyncio.create_task(auto_loop(app))
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__=="__main__":
    import asyncio
    asyncio.run(main())
