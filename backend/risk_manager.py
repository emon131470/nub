RISK_FRACTION = 0.01
DAILY_LOSS_FRACTION = 0.03
MAX_OPEN_TRADES = 1
SL_ATR_MULTIPLIER = 1.5
REWARD_RISK = 2.0

def build_levels(side, price, atr):
    distance = atr * SL_ATR_MULTIPLIER
    if distance <= 0:
        raise ValueError("ATR is invalid.")
    if side == "BUY":
        return price - distance, price + distance * REWARD_RISK
    return price + distance, price - distance * REWARD_RISK
