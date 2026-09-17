import os, json, time, hmac, hashlib, base64, asyncio, re, threading
from datetime import datetime
import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram import Update
from flask import Flask

app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "Trader PRO Futures v1.6 Fixed - OK"

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

for path in [".env","/data/data/com.termux/files/home/secure-bot/.env"]:
    clean_env(path)
try:
    from dotenv import load_dotenv; load_dotenv(override=True)
except: pass

BOT_TOKEN=os.getenv("BOT_TOKEN","").strip() or os.getenv("TELEGRAM_BOT_TOKEN","").strip()
API_KEY=os.getenv("BITGET_API_KEY","").strip()
SECRET_KEY=os.getenv("BITGET_SECRET_KEY","").strip() or os.getenv("BITGET_API_SECRET","").strip()
PASSPHRASE=os.getenv("BITGET_PASSPHRASE","").strip() or os.getenv("BITGET_API_PASSPHRASE","").strip() or os.getenv("BITGET_PASSPHRASE_API","").strip()

MY_ID=7679796977
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
    d={"pair":"BTC/USDT","alloc":10.0,"mode":"DEMO","auto":False,"demo_bal":100.0,"real_bal":0.0,"trades":[],"start":time.time(),"paused":{},"positions":{},"leverage":10,"side":"BOTH","awaiting_alloc":False}
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

async def is_allowed(u): return u.effective_user.id==MY_ID

def bitget_sign(ts, method, path, body=""):
    msg=f"{ts}{method}{path}{body}"
    return base64.b64encode(hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).digest()).decode()

async def get_futures_balance():
    if not API_KEY or not SECRET_KEY or not PASSPHRASE:
        return None, "No API keys - check ENV"
    try:
        ts=str(int(time.time()*1000))
        path="/api/v2/mix/account/accounts?productType=USDT-FUTURES"
        sign=bitget_sign(ts, "GET", path, "")
        headers={"ACCESS-KEY": API_KEY.strip(),"ACCESS-SIGN": sign,"ACCESS-TIMESTAMP": ts,"ACCESS-PASSPHRASE": PASSPHRASE.strip(),"Content-Type":"application/json"}
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.get(f"https://api.bitget.com{path}", headers=headers)
            txt=r.text[:600]
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
                return None, f"Bitget {data.get('msg','')} code={data.get('code')} {txt[:250]}"
            return None, f"HTTP {r.status_code}: {txt[:300]} Key{len(API_KEY)} Sec{len(SECRET_KEY)}"
    except Exception as e:
        return None, f"Exc {e}"

async def get_futures_positions_live():
    if not API_KEY or not SECRET_KEY or not PASSPHRASE: return [], "No API"
    try:
        ts=str(int(time.time()*1000))
        path="/api/v2/mix/position/all-position?productType=USDT-FUTURES"
        sign=bitget_sign(ts, "GET", path, "")
        headers={"ACCESS-KEY": API_KEY.strip(),"ACCESS-SIGN": sign,"ACCESS-TIMESTAMP": ts,"ACCESS-PASSPHRASE": PASSPHRASE.strip(),"Content-Type":"application/json"}
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.get(f"https://api.bitget.com{path}", headers=headers)
            if r.status_code==200:
                data=r.json()
                if data.get("code")=="00000": return data.get("data",[]), None
                return [], f"API {data.get('msg','')} {str(data)[:200]}"
            return [], f"HTTP {r.status_code} {r.text[:300]}"
    except Exception as e:
        return [], str(e)

async def set_futures_leverage(symbol, leverage):
    """Set leverage before opening - Bitget requires this"""
    if not API_KEY or not SECRET_KEY or not PASSPHRASE: return True
    try:
        ts=str(int(time.time()*1000))
        path="/api/v2/mix/account/set-leverage"
        body={"symbol": symbol, "productType": "USDT-FUTURES", "marginCoin": "USDT", "leverage": str(leverage), "marginMode": "isolated"}
        body_json=json.dumps(body)
        sign=bitget_sign(ts, "POST", path, body_json)
        headers={"ACCESS-KEY": API_KEY.strip(),"ACCESS-SIGN": sign,"ACCESS-TIMESTAMP": ts,"ACCESS-PASSPHRASE": PASSPHRASE.strip(),"Content-Type":"application/json"}
        async with httpx.AsyncClient(timeout=10) as c:
            r=await c.post(f"https://api.bitget.com{path}", headers=headers, content=body_json)
            # Ignore errors - leverage may already be set
            return True
    except: return True

async def open_futures_position_live(symbol, side, alloc_usdt, leverage, price):
    """Open real futures position on Bitget LIVE - FIXED size calc for BTC/PEPE"""
    if not API_KEY or not SECRET_KEY or not PASSPHRASE: return False, "No API keys"
    try:
        # FIX 1: Set leverage first
        await set_futures_leverage(symbol, leverage)

        # FIX 2: Correct size calculation - handle BTC (small) vs PEPE (large) properly
        # notional = alloc * lev, size = notional / price in base coin
        notional = alloc_usdt * leverage
        size = notional / price if price>0 else 0
        if size<=0: return False, f"Invalid size price={price} alloc={alloc_usdt}"

        # FIX 3: Proper precision per symbol - critical bug fix for BTC
        # PEPE: needs integer millions, BTC: needs 0.0001 precision
        if "PEPE" in symbol or "SHIB" in symbol:
            # Meme coins: integer, min 1
            size_str = str(int(size))
        elif "BTC" in symbol or "ETH" in symbol:
            # Major coins: 4-6 decimals, min 0.0001
            size_str = f"{size:.6f}".rstrip('0').rstrip('.')
            if float(size_str)<0.0001: size_str="0.0001"
        elif price>=1000: # BTC ~60000
            size_str = f"{size:.5f}".rstrip('0').rstrip('.')
        elif price>=1: # SOL, BNB etc
            size_str = f"{size:.3f}".rstrip('0').rstrip('.')
        else:
            # Low price coins: 2 decimals or integer
            if size>1000: size_str=str(int(size))
            else: size_str=f"{size:.2f}".rstrip('0').rstrip('.')

        # FIX 4: Validate notional minimum - Bitget min $5 for futures
        if notional < 4.5:
            return False, f"Min notional $5 needed, you have ${notional:.2f} (alloc ${alloc_usdt} x{leverage}) - increase alloc to $5+"

        ts=str(int(time.time()*1000))
        path="/api/v2/mix/order/place-order"
        order_side = "buy" if side=="LONG" else "sell"
        body = {
            "symbol": symbol,
            "productType": "USDT-FUTURES",
            "marginMode": "isolated",
            "marginCoin": "USDT",
            "size": size_str,
            "side": order_side,
            "tradeSide": "open",
            "orderType": "market",
            "force": "gtc"
        }
        body_json=json.dumps(body)
        sign=bitget_sign(ts, "POST", path, body_json)
        headers={"ACCESS-KEY": API_KEY.strip(),"ACCESS-SIGN": sign,"ACCESS-TIMESTAMP": ts,"ACCESS-PASSPHRASE": PASSPHRASE.strip(),"Content-Type":"application/json"}
        async with httpx.AsyncClient(timeout=20) as c:
            r=await c.post(f"https://api.bitget.com{path}", headers=headers, content=body_json)
            txt=r.text[:800]
            if r.status_code==200:
                data=r.json()
                if data.get("code")=="00000": return True, None
                # Detailed error for debugging
                return False, f"Bitget {data.get('msg','')} code={data.get('code')} size={size_str} notional=${notional:.2f} {txt[:250]}"
            return False, f"HTTP {r.status_code} size={size_str} {txt[:350]}"
    except Exception as e:
        return False, f"Exc {e}"

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
                return False, f"{data.get('msg','')} {str(data)[:300]}"
            return False, f"HTTP {r.status_code} {r.text[:300]}"
    except Exception as e:
        return False, str(e)

async def get_prices():
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r=await c.get("https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES")
            if r.status_code==200:
                data=r.json()
                if data.get("code")=="00000":
                    out={}
                    tickers=data.get("data",[])
                    mp={t["symbol"]: float(t["lastPr"]) for t in tickers}
                    for label, info in PAIRS.items():
                        sym=info["sym"]
                        for k,v in mp.items():
                            if k.startswith(sym):
                                out[label]=(v, 0)
                                break
                    if out: return out, "Bitget Futures"
    except: pass
    try:
        ids=",".join([v["cg"] for v in PAIRS.values()])
        url=f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
        async with httpx.AsyncClient(timeout=12) as c:
            r=await c.get(url)
            if r.status_code==200:
                data=r.json()
                out={}
                for label, info in PAIRS.items():
                    cg=info["cg"]
                    if cg in data and "usd" in data[cg]:
                        out[label]=(float(data[cg]["usd"]), 0)
                if out: return out, "CoinGecko"
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
        overbought_extreme=rsi>85  # Keep original 85 RSI as user requested
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
                    try: await app.bot.send_message(chat_id=MY_ID, text=f"⚠️ FUTURES {pair_label} PUMP +{chg5:.1f}% -> BUY paused {dur//60}min")
                    except: pass
                    continue
                if chg5<-15:
                    s["paused"][pair_label]={"until":time.time()+dur,"reason":f"RUG {chg5:.1f}%","pct":chg5}; save_state(s)
                    try: await app.bot.send_message(chat_id=MY_ID, text=f"🚨 FUTURES {pair_label} RUG {chg5:.1f}% -> paused {dur//3600:.1f}h")
                    except: pass
        positions=s.get("positions",{}); pos=positions.get(pair_label)
        if sig=="BUY" and not pos:
            price=info["price"]
            lev=s.get("leverage",10)
            alloc=s["alloc"]
            # LIVE MODE: Place REAL order on Bitget - LONG
            if s["mode"]=="LIVE":
                sym_real=PAIRS.get(pair_label,{}).get("sym", pair_label.replace("/",""))
                ok,err=await open_futures_position_live(sym_real, "LONG", alloc, lev, price)
                if not ok:
                    try: await app.bot.send_message(chat_id=MY_ID, text=f"❌ LIVE OPEN FAIL LONG {pair_label} x{lev} ${alloc} - {err}\nCheck: Futures balance, min size, API permissions (Read+Trade)")
                    except: pass
                    s["paused"][pair_label]={"until":time.time()+600,"reason":f"OPEN FAIL {err[:30]}","pct":0}
                    save_state(s)
                    continue
                else:
                    bal,_=await get_futures_balance()
                    if bal is not None: s["real_bal"]=bal
            positions[pair_label]={"price":price,"alloc":alloc,"time":time.time(),"high":price,"low":price,"rsi":info["rsi"],"side":"LONG","lev":lev}
            s["positions"]=positions
            if s["mode"]=="DEMO":
                if s["demo_bal"]>=alloc:
                    s["demo_bal"]-=alloc
                    s["trades"].append({"type":"BUY LONG","pair":pair_label,"price":price,"time":datetime.now().strftime("%H:%M"),"rsi":info["rsi"]})
            else:
                s["trades"].append({"type":"BUY LONG LIVE","pair":pair_label,"price":price,"time":datetime.now().strftime("%H:%M"),"rsi":info["rsi"],"reason":"REAL OPEN OK"})
            save_state(s)
            try: await app.bot.send_message(chat_id=MY_ID, text=f"🟢 LONG {pair_label} @ {format_price(price)} RSI {info['rsi']:.0f} SMA10 {format_price(info['sma10'])}>{format_price(info['sma30'])} x{lev} {s['mode']}")
            except: pass

        elif sig=="SELL" and not pos:
            # OPTION B: Enable SHORT on SELL signal - same hybrid RSI 85 logic
            price=info["price"]
            lev=s.get("leverage",10)
            alloc=s["alloc"]
            # LIVE MODE: Place REAL SHORT order
            if s["mode"]=="LIVE":
                sym_real=PAIRS.get(pair_label,{}).get("sym", pair_label.replace("/",""))
                ok,err=await open_futures_position_live(sym_real, "SHORT", alloc, lev, price)
                if not ok:
                    try: await app.bot.send_message(chat_id=MY_ID, text=f"❌ LIVE OPEN FAIL SHORT {pair_label} x{lev} ${alloc} - {err}\nCheck: Futures balance, min size, API permissions (Read+Trade)")
                    except: pass
                    s["paused"][pair_label]={"until":time.time()+600,"reason":f"OPEN FAIL SHORT {err[:30]}","pct":0}
                    save_state(s)
                    continue
                else:
                    bal,_=await get_futures_balance()
                    if bal is not None: s["real_bal"]=bal
            # Create SHORT tracking
            positions[pair_label]={"price":price,"alloc":alloc,"time":time.time(),"high":price,"low":price,"rsi":info["rsi"],"side":"SHORT","lev":lev}
            s["positions"]=positions
            if s["mode"]=="DEMO":
                if s["demo_bal"]>=alloc:
                    s["demo_bal"]-=alloc
                    s["trades"].append({"type":"SELL SHORT","pair":pair_label,"price":price,"time":datetime.now().strftime("%H:%M"),"rsi":info["rsi"],"reason":info.get("sell_reason","RSI 85")})
            else:
                s["trades"].append({"type":"SELL SHORT LIVE","pair":pair_label,"price":price,"time":datetime.now().strftime("%H:%M"),"rsi":info["rsi"],"reason":"REAL SHORT OPEN OK "+info.get("sell_reason","")})
            save_state(s)
            try: await app.bot.send_message(chat_id=MY_ID, text=f"🔴 SHORT {pair_label} @ {format_price(price)} RSI {info['rsi']:.0f} {info.get('sell_reason','')} SMA10 {format_price(info['sma10'])}<{format_price(info['sma30'])} x{lev} {s['mode']}")
            except: pass

        elif pos:
            entry=pos["price"]; cur=info["price"]; side=pos.get("side","LONG"); lev=pos.get("lev",10)
            if side=="LONG": raw_pct=(cur-entry)/entry*100; pnl_pct=raw_pct*lev
            else: raw_pct=(entry-cur)/entry*100; pnl_pct=raw_pct*lev
            if cur>pos.get("high",entry): pos["high"]=cur
            if cur<pos.get("low",entry): pos["low"]=cur
            open_time=pos.get("time", time.time()); held_min=(time.time()-open_time)/60
            positions[pair_label]=pos; s["positions"]=positions
            should_sell=False; reason=""
            # 1. HARD LIQ PROTECTION
            if pnl_pct<=-80: should_sell=True; reason=f"LIQ STOP {pnl_pct:.1f}% Held {held_min:.0f}m"
            # 2. Keep original 85 RSI logic for normal sells
            # 3. NEW: 5HR MAX force close as user requested - no matter RSI
            elif held_min>=300: # 5 hours max
                should_sell=True; reason=f"FORCE 5HR MAX CLOSE Held {held_min:.0f}m PnL {pnl_pct:+.2f}% raw {raw_pct:+.2f}%"
            else:
                # Original 85 RSI SELL logic preserved
                if side=="LONG":
                    if sig=="SELL":
                        if raw_pct>=0.6 or pnl_pct<=-35 or info["rsi"]>75:
                            should_sell=True; reason=f"{info.get('sell_reason','Sell')} TP {pnl_pct:.1f}% raw {raw_pct:.1f}% Held {held_min:.0f}m"
                else:
                    if sig=="BUY":
                        if raw_pct>=0.6 or pnl_pct<=-35 or info["rsi"]<25:
                            should_sell=True; reason=f"Reversal TP {pnl_pct:.1f}% raw {raw_pct:.1f}% Held {held_min:.0f}m"
            # Trailing still works
            high=pos.get("high",entry); low=pos.get("low",entry)
            if side=="LONG" and high>entry*1.05:
                trail=high*0.97
                if cur<=trail and raw_pct>1: should_sell=True; reason=f"TRAIL LONG {pnl_pct:.1f}% from {format_price(high)} Held {held_min:.0f}m"
            elif side=="SHORT" and low < entry*0.95:
                trail=low*1.03
                if cur>=trail and raw_pct>1: should_sell=True; reason=f"TRAIL SHORT {pnl_pct:.1f}% from {format_price(low)} Held {held_min:.0f}m"
            if should_sell:
                if s["mode"]=="DEMO":
                    profit=s["alloc"]*(raw_pct/100)*lev
                    s["demo_bal"]+=s["alloc"]+profit
                    s["trades"].append({"type":"CLOSE","pair":pair_label,"price":cur,"time":datetime.now().strftime("%H:%M"),"pnl":pnl_pct,"raw":raw_pct,"reason":reason,"side":side})
                else:
                    # LIVE real close
                    sym_real=PAIRS.get(pair_label,{}).get("sym", pair_label.replace("/",""))
                    ok,err=await close_futures_position_live(sym_real, side)
                    if ok:
                        s["trades"].append({"type":"CLOSE LIVE","pair":pair_label,"price":cur,"time":datetime.now().strftime("%H:%M"),"pnl":pnl_pct,"raw":raw_pct,"reason":reason+" REAL CLOSE","side":side})
                        bal,_=await get_futures_balance()
                        if bal is not None: s["real_bal"]=bal
                    else:
                        s["trades"].append({"type":"CLOSE FAIL","pair":pair_label,"price":cur,"time":datetime.now().strftime("%H:%M"),"pnl":pnl_pct,"raw":raw_pct,"reason":f"{reason} FAIL {err}","side":side})
                del positions[pair_label]; s["positions"]=positions; save_state(s)
                try: await app.bot.send_message(chat_id=MY_ID, text=f"💰 CLOSE {side} {pair_label} @ {format_price(cur)} {reason} PnL {pnl_pct:+.2f}% x{lev} raw {raw_pct:+.2f}% Held {held_min:.0f}m")
                except: pass
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
    lev=s.get("leverage",10)
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
        pos_txt=" ".join([f"{v.get('side','LONG')} {k}" for k,v in s.get("positions",{}).items()])
        buttons.append([InlineKeyboardButton(f"🔴 CLOSE {pos_txt[:25]}", callback_data="close_pos")])
    else:
        if s["mode"]=="LIVE":
            buttons.append([InlineKeyboardButton("🔴 CLOSE LIVE Position", callback_data="close_live")])
        else:
            buttons.append([InlineKeyboardButton("🔴 CLOSE (No Pos)", callback_data="close_pos")])
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update): return
    s=load_state()
    if s["mode"]=="LIVE":
        bal,_=await get_futures_balance()
        if bal is not None: s["real_bal"]=bal; save_state(s)
        bal_txt=f"LIVE ${s.get('real_bal',0):.2f}"
    else: bal_txt=f"Demo ${s['demo_bal']:.2f}"
    uptime=format_uptime(s.get("start", time.time()))
    txt=f"⚡ Trader PRO Futures v1.11 LONG+SHORT + Hybrid SMA RSI 85 + 5HR MAX\nPair: {s['pair']} Lev: x{s.get('leverage',10)}\nMode: {s['mode']} Auto: {'ON' if s['auto'] else 'OFF'}\n{bal_txt}\nAlloc: ${s['alloc']}\n⏱ Uptime: {uptime}\nStarted: {datetime.fromtimestamp(s.get('start',time.time())).strftime('%Y-%m-%d %H:%M')}\nFix: LONG+SHORT both, RSI 85, SMA 10/30 cross, 5HR MAX, LIVE real open"
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
        await q.edit_message_text("Select alloc $:", reply_markup=InlineKeyboardMarkup(btns))
    elif data.startswith("setalloc_"):
        s["alloc"]=float(data.replace("setalloc_","")); save_state(s)
        await q.edit_message_text(f"Alloc ${s['alloc']}", reply_markup=kb(s))
    elif data=="lev":
        btns=[[InlineKeyboardButton(f"x{a}", callback_data=f"setlev_{a}") for a in [5,10,20,30,50]]]
        btns.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
        await q.edit_message_text("Select leverage:", reply_markup=InlineKeyboardMarkup(btns))
    elif data.startswith("setlev_"):
        s["leverage"]=int(data.replace("setlev_","")); save_state(s)
        await q.edit_message_text(f"Leverage x{s['leverage']}", reply_markup=kb(s))
    elif data=="switch":
        old_mode=s["mode"]
        new_mode="LIVE" if old_mode=="DEMO" else "DEMO"
        s["mode"]=new_mode
        # FIX: Auto should be OFF when switching modes - don't carry DEMO auto to LIVE
        s["auto"]=False
        if new_mode=="LIVE":
            bal,err=await get_futures_balance()
            s["real_bal"]=bal if bal is not None else 0.0
        save_state(s)
        mode_txt=f"🔴 LIVE ${s.get('real_bal',0):.2f}\n⚪ AUTO OFF (switched from {old_mode})" if new_mode=="LIVE" else f"🧪 DEMO ${s['demo_bal']:.2f}\n⚪ AUTO OFF (switched from {old_mode})"
        await q.edit_message_text(f"Switched to {mode_txt}\n\nPress AUTO ON to start {new_mode}", reply_markup=kb(s))
    elif data=="auto":
        s["auto"]=not s["auto"]; save_state(s)
        await q.edit_message_text(f"Auto {'ON' if s['auto'] else 'OFF'}", reply_markup=kb(s))
    elif data=="bal":
        if s["mode"]=="DEMO":
            pos=s.get("positions",{}); prices,_=await get_prices()
            txt=f"🧪 DEMO Bal ${s['demo_bal']:.2f}\n"
            if pos:
                for k,v in pos.items():
                    cur=prices.get(k,(v["price"],0))[0] if prices.get(k) else v["price"]
                    entry=v["price"]; side=v.get("side","LONG"); lev=v.get("lev",10)
                    raw=(cur-entry)/entry*100 if side=="LONG" else (entry-cur)/entry*100
                    pnl=raw*lev
                    held=(time.time()-v.get("time",time.time()))/60
                    txt+=f"\n📍 {k} {side} x{lev}\nEntry {format_price(entry)} Now {format_price(cur)}\nPnL {pnl:+.2f}% raw {raw:+.2f}% Held {held:.0f}m\n"
            else: txt+="No positions"
            await q.edit_message_text(txt, reply_markup=kb(s))
        else:
            await q.edit_message_text("🔄 Fetching LIVE...")
            bal,err=await get_futures_balance(); live_pos,perr=await get_futures_positions_live()
            if err and bal is None:
                await q.edit_message_text(f"❌ {err}\n\nCheck API: Read-write + Futures Holdings+Order, blank IP, USDT in Futures", reply_markup=kb(s))
            else:
                if bal is not None: s["real_bal"]=bal; save_state(s)
                txt=f"🔴 LIVE Bal ${s.get('real_bal',0):.2f}\n"
                if live_pos:
                    total=0
                    for p in live_pos:
                        try:
                            sym=p.get("symbol",""); side=p.get("holdSide",""); entry=float(p.get("averageOpenPrice",0) or 0); mark=float(p.get("markPrice",0) or 0); upnl=float(p.get("unrealizedPL",0) or 0); lev=int(float(p.get("leverage",10))); total+=upnl
                            txt+=f"{sym} {side} x{lev} Entry {format_price(entry)} Mark {format_price(mark)} uPnL ${upnl:+.2f}\n"
                        except: pass
                    txt+=f"\nTotal uPnL ${total:+.2f}"
                else: txt+="No real positions"
                await q.edit_message_text(txt, reply_markup=kb(s))
    elif data=="prices":
        prices,src=await get_prices()
        txt=f"📊 MARKETS ({src}) - ALL 20 Pairs\n{datetime.now().strftime('%H:%M:%S')}\n\n"
        for k in PAIRS.keys():
            if k in prices:
                price=prices[k][0]
                emoji=PAIRS[k].get("emoji","")
                paused=" ⏸" if k in s.get("paused",{}) else ""
                txt+=f"{emoji} {k}: {format_price(price)}{paused}\n"
            else:
                txt+=f"{PAIRS[k].get('emoji','')} {k}: --\n"
        await q.edit_message_text(txt, reply_markup=kb(s))
    elif data=="pnl":
        if s["mode"]=="LIVE":
            live_pos,perr=await get_futures_positions_live(); bal,_=await get_futures_balance()
            txt=f"🔴 LIVE PnL Bal ${bal or s.get('real_bal',0):.2f}\n"
            if live_pos:
                for p in live_pos:
                    try: txt+=f"{p.get('symbol','')} uPnL ${float(p.get('unrealizedPL',0) or 0):+.2f}\n"
                    except: pass
            trades=s.get("trades",[])[-10:]; txt+="\nBot trades:\n"
            for t in trades[-5:]: txt+=f"{t.get('type','')} {t.get('pair','')} {t.get('pnl',0):+.2f}% {t.get('reason','')[:30]}\n"
            await q.edit_message_text(txt or "No PnL", reply_markup=kb(s))
        else:
            trades=s.get("trades",[])[-10:]; txt=f"🧪 DEMO PnL Bal ${s['demo_bal']:.2f}\n"
            for t in trades: txt+=f"{t['type']} {t['pair']} {t.get('pnl',0):+.2f}% {t.get('reason','')[:25]}\n"
            await q.edit_message_text(txt or "No trades", reply_markup=kb(s))
    elif data=="paused":
        paused=s.get("paused",{}); txt="Paused:\n" if paused else "No paused"
        for k,v in paused.items(): txt+=f"{k}: {v['reason']} until {datetime.fromtimestamp(v['until']).strftime('%H:%M')}\n"
        await q.edit_message_text(txt, reply_markup=kb(s))
    elif data=="close_pos":
        positions=s.get("positions",{})
        if not positions: await q.edit_message_text("No bot positions.\nUse CLOSE LIVE Position for real Bitget pos", reply_markup=kb(s))
        else:
            await q.edit_message_text("🔄 Closing...")
            prices,_=await get_prices(); txt="💰 CLOSE:\n\n"; total=0
            for pair,pos in list(positions.items()):
                cur=prices.get(pair,(pos["price"],0))[0] if prices.get(pair) else pos["price"]
                entry=pos["price"]; alloc=pos["alloc"]; side=pos.get("side","LONG"); lev=pos.get("lev",10); sym=PAIRS.get(pair,{}).get("sym","")
                raw=(cur-entry)/entry*100 if side=="LONG" else (entry-cur)/entry*100; pnl=raw*lev; profit=alloc*raw/100*lev
                close_ok=True
                if s["mode"]=="LIVE":
                    ok,err=await close_futures_position_live(sym, side)
                    if not ok: close_ok=False; txt+=f"❌ LIVE FAIL {pair}: {err}\n"
                    else: txt+=f"✅ REAL CLOSE {pair}\n"; bal,_=await get_futures_balance()
                    if bal is not None: s["real_bal"]=bal
                if s["mode"]=="DEMO": s["demo_bal"]+=alloc+profit; total+=profit
                else:
                    if close_ok: total+=profit
                txt+=f"{pair} {side} x{lev} {entry:.4f}->{cur:.4f} {pnl:+.2f}%\n"
                s["trades"].append({"type":"CLOSE MANUAL","pair":pair,"price":cur,"time":datetime.now().strftime("%H:%M"),"pnl":pnl,"raw":raw,"reason":"MANUAL","side":side})
                del s["positions"][pair]; s["paused"][pair]={"until":time.time()+7200,"reason":"MANUAL CLOSE","pct":raw}
            s["auto"]=False; save_state(s)
            txt+=f"\nBal ${s['demo_bal'] if s['mode']=='DEMO' else s.get('real_bal',0):.2f} Total ${total:+.2f}\n⏸ AUTO OFF + paused 2h"
            await q.edit_message_text(txt, reply_markup=kb(s))
    elif data=="close_live":
        await q.edit_message_text("🔄 Checking real positions on Bitget...")
        live_pos,perr=await get_futures_positions_live()
        if perr:
            # API error - likely Read-Only key or no permission
            txt=f"❌ Bitget API Error: {perr}\n\nIf you see 'permission' or 'auth' error:\nGo to Bitget -> API -> Edit -> Tick 'Read' + 'Trade' (Read-Write)\nAlso clear IP whitelist or add server IP\n\n"
            # Also clear local tracking to fix ghost positions
            if s.get("positions"):
                txt+=f"\n⚠️ Clearing {len(s['positions'])} ghost local positions to sync\n"
                s["positions"]={}
                s["auto"]=False
                save_state(s)
                txt+=f"✅ Cleared. New Bal ${s.get('real_bal',0):.2f}\nAUTO OFF"
            await q.edit_message_text(txt, reply_markup=kb(s))
        elif not live_pos:
            txt="No real positions on Bitget Futures\n\n"
            # Also clear local bot tracking if exists (sync)
            if s.get("positions"):
                txt+=f"But bot has {len(s['positions'])} local tracked positions (ghost).\nClearing them to sync with real exchange...\n"
                for pair,pos in list(s["positions"].items()):
                    txt+=f" - {pair} {pos.get('side')} cleared\n"
                s["positions"]={}
                s["auto"]=False
                save_state(s)
                txt+=f"\n✅ Synced. Local positions cleared.\nBal ${s.get('real_bal',0):.2f}\nAUTO OFF"
            else:
                txt+="Both Bitget and bot have no positions. OK"
            await q.edit_message_text(txt, reply_markup=kb(s))
        else:
            txt="Closing REAL positions:\n\n"
            for p in live_pos:
                try:
                    sym=p.get("symbol",""); side=p.get("holdSide",""); mark=float(p.get("markPrice",0) or 0)
                    ok,err=await close_futures_position_live(sym, side)
                    if ok:
                        txt+=f"✅ {sym} {side} closed @ {format_price(mark)}\n"
                    else:
                        txt+=f"❌ {sym} {side} FAIL: {err}\n"
                        if "permission" in str(err).lower() or "auth" in str(err).lower():
                            txt+=f"  -> Fix: Bitget API needs Read-Write (Trade) permission!\n"
                except Exception as e: txt+=f"❌ {e}\n"
            bal,_=await get_futures_balance()
            if bal is not None: s["real_bal"]=bal
            s["auto"]=False; s["positions"]={}; save_state(s)
            txt+=f"\nNew Bal ${s.get('real_bal',0):.2f}\nAUTO OFF - positions cleared"
            await q.edit_message_text(txt, reply_markup=kb(s))
    elif data=="uptime":
        uptime=format_uptime(s.get("start", time.time()))
        started=datetime.fromtimestamp(s.get("start", time.time())).strftime('%Y-%m-%d %H:%M:%S')
        txt=f"⏱ BOT UPTIME\n\nUptime: {uptime}\nStarted: {started}\nNow: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nTrades: {len(s.get('trades',[]))}\nPositions: {len(s.get('positions',{}))}\nMode: {s['mode']}\nAuto: {'ON' if s['auto'] else 'OFF'}\nBalance: ${s.get('demo_bal',0):.2f} DEMO / ${s.get('real_bal',0):.2f} LIVE"
        await q.edit_message_text(txt, reply_markup=kb(s))
    elif data=="back":
        await q.edit_message_text(f"⚡ Futures v1.7 {s['pair']} x{s.get('leverage',10)}", reply_markup=kb(s))

async def close_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update): return
    s=load_state(); positions=s.get("positions",{})
    if not positions: await update.message.reply_text("No positions", reply_markup=kb(s)); return
    prices,_=await get_prices(); txt="💰 MANUAL CLOSE REAL:\n\n"; total=0
    for pair,pos in list(positions.items()):
        cur=prices.get(pair,(pos["price"],0))[0] if prices.get(pair) else pos["price"]
        entry=pos["price"]; alloc=pos["alloc"]; side=pos.get("side","LONG"); lev=pos.get("lev",10); sym=PAIRS.get(pair,{}).get("sym","")
        raw=(cur-entry)/entry*100 if side=="LONG" else (entry-cur)/entry*100; pnl=raw*lev; profit=alloc*raw/100*lev
        if s["mode"]=="LIVE":
            ok,err=await close_futures_position_live(sym, side)
            txt+=f"{'✅' if ok else '❌'} {sym} {side} {err or ''}\n"
            if ok:
                bal,_=await get_futures_balance()
                if bal is not None: s["real_bal"]=bal
                total+=profit
        else: s["demo_bal"]+=alloc+profit; total+=profit
        txt+=f"{pair} {side} {entry:.4f}->{cur:.4f} PnL {pnl:+.2f}%\n"
        s["trades"].append({"type":"CLOSE","pair":pair,"price":cur,"time":datetime.now().strftime("%H:%M"),"pnl":pnl,"raw":raw,"reason":"MANUAL /close","side":side})
        del s["positions"][pair]; s["paused"][pair]={"until":time.time()+7200,"reason":"MANUAL CLOSE","pct":raw}
    s["auto"]=False; save_state(s)
    txt+=f"\nBal ${s['demo_bal'] if s['mode']=='DEMO' else s.get('real_bal',0):.2f} Total ${total:+.2f}\nAUTO OFF"
    await update.message.reply_text(txt, reply_markup=kb(s))

async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update): return
    s=load_state(); save_state(s)
    try:
        with open(get_state_path(),'rb') as f:
            await update.message.reply_document(document=f, filename="futures_state_backup.json", caption=f"Backup {datetime.now()}")
    except: await update.message.reply_text(f"BACKUP {json.dumps(s)[:3000]}", reply_markup=kb(s))

async def import_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update): return
    if update.message.document:
        try:
            file=await context.bot.get_file(update.message.document.file_id); data=await file.download_as_bytearray()
            j=json.loads(data.decode()); save_state(j)
            await update.message.reply_text(f"✅ Restored Bal ${j.get('demo_bal',0):.2f}", reply_markup=kb(j)); return
        except Exception as e: await update.message.reply_text(f"❌ {e}"); return
    await update.message.reply_text("Send backup json + /import")

async def main():
    threading.Thread(target=lambda: app_flask.run(host='0.0.0.0', port=8080), daemon=True).start()
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("close", close_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("backup", export_cmd))
    app.add_handler(CommandHandler("import", import_cmd))
    app.add_handler(CallbackQueryHandler(cb))
    await app.initialize(); await app.start()
    asyncio.create_task(auto_loop(app))
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__=="__main__":
    import asyncio
    asyncio.run(main())
