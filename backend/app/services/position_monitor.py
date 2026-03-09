def check_break_even(position, price):
    if not position.get("be_moved"):
        if position["side"] == "buy" and price >= position["be_trigger"]:
            position["sl"] = position["entry"]
            position["be_moved"] = True
            print(f"[{position['symbol']}] Break-even triggered. SL moved to {position['sl']}")

        if position["side"] == "sell" and price <= position["be_trigger"]:
            position["sl"] = position["entry"]
            position["be_moved"] = True
            print(f"[{position['symbol']}] Break-even triggered. SL moved to {position['sl']}")

    return position

def reverse_trade(position):
    entry = position["sl"]
    sl = position["entry"]

    risk = abs(sl - entry)

    if position["side"] == "buy":
        new_side = "sell"
        tp = entry - risk
    else:
        new_side = "buy"
        tp = entry + risk
        
    print(f"[{position['symbol']}] Reversing trade to {new_side}. Entry: {entry}, SL: {sl}, TP: {tp}")

    return {
        "symbol": position["symbol"],
        "side": new_side,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "be_trigger": entry - (risk * 0.35) if new_side == "sell" else entry + (risk * 0.35),
        "be_moved": False,
        "is_reversal": True
    }
