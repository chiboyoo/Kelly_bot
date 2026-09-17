README - Deekelzo FX Futures PRO v2.0
========================================

Professional Telegram trading bot for Bitget USDT-Futures with LONG+SHORT strategy.

FEATURES:
- Hybrid signal: RSI 30-58 dip + SMA 10/30 golden cross for LONG, RSI 85 extreme + death cross for SHORT
- 20 pairs: BTC, ETH, SOL, BNB, XRP, DOGE, SHIB, PEPE, etc.
- Risk management:
  * PUMP +15% in 5min pauses new LONGs (anti-FOMO)
  * RUG -15% pauses for 2h (meme) / 2-24h
  * Trailing 3% locks pump profits
  * 5HR MAX force close (no bag holding)
  * -35% PnL cut loss on signal, -80% emergency LIQ stop
- DEMO/LIVE switch with AUTO OFF safety
- Real Bitget API: balance, positions, market orders
- Buttons: Markets (20 prices), Trades, Paused, Uptime, Close

SETUP FOR BUYER:

1. Create Telegram bot:
   - Talk to @BotFather -> /newbot -> get BOT_TOKEN

2. Get Telegram User ID:
   - Talk to @userinfobot -> get your numeric ID -> this is OWNER_ID

3. Create Bitget API (NO WITHDRAW permission):
   - Bitget App -> API Management -> Create API
   - Permissions: Read + Trade (Futures Order + Holdings + Spot Order)
   - IP whitelist: Leave BLANK (easiest for cloud hosting)
   - Save API_KEY, SECRET_KEY, PASSPHRASE

4. Hosting (justrunmyapp / Render / VPS):
   ENV VARS to set:
     BOT_TOKEN=123456:ABC...
     BITGET_API_KEY=bg_...
     BITGET_SECRET_KEY=...
     BITGET_PASSPHRASE=...
     OWNER_ID=7679796977 (your telegram ID)

5. Deploy:
   - Upload FUTURES_BOT_PRO_SALE_READY.py as main.py
   - Start command: python main.py
   - Health check port 8080 (Flask)

6. Telegram:
   - /start -> To DEMO -> AUTO ON -> test with DEMO $100
   - Check Markets shows ALL 20 pairs with price $0.00000351 format
   - Switch to LIVE -> AUTO OFF safety -> check LIVE $ balance
   - AUTO ON in LIVE -> real orders placed

SECURITY FOR SELLING:
- No hardcoded IDs - uses OWNER_ID env var
- No personal Termux paths
- No API key length leaks
- Never request withdraw permission
- State file survives restarts at /data/bot_state_futures.json

CUSTOMIZATION:
- Change PAIRS dict to add/remove coins
- Adjust leverage options in lev button: [3,5,10,20]
- Adjust alloc: [1,5,10,20,50,100]
- Change RSI thresholds in calc_signal_hybrid (currently 30-58 buy, 85 sell)
- Change PUMP threshold (currently 15% in 5min)

TROUBLESHOOTING:
- "No API keys" -> check ENV vars spelling
- "permission" error on close -> Bitget API needs Read+Trade + Futures Holdings, and IP blank
- "Min notional $5" -> increase alloc to $5+ (Bitget futures minimum)
- Button stuck on CLOSE LIVE -> click Clear Ghost
- LIVE balance 0 but should have $ -> transfer Funding -> Futures account in Bitget

DISCLAIMER:
This software is for educational purposes. Trading futures is high risk, you can lose more than initial margin.
No guarantee of profit. Use isolated margin, start with small $1-$5 alloc, test DEMO first.
Seller not responsible for losses. Buyer assumes all risk.

LICENSE:
MIT License for personal use. Commercial resale or distribution as SaaS requires written permission from original author.
You may modify for your own trading.

Support: Provide 1-time setup help, no ongoing financial advice.

Changelog:
v2.0 SALE READY - Fixed BTC size bug (was 1 BTC), added leverage set API, added OWNER_ID env, removed personal paths, added Clear Ghost, LONG+SHORT, 5HR MAX, separate AUTO OFF
v1.12 - Audited version with all fixes
v1.11 - LONG+SHORT enabled
v1.10 - LIVE real open fix

Contact: [Your contact for buyers]
