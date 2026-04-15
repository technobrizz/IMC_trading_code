from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json

class Trader:
    def run(self, state: TradingState):
        result = {}
        # Position limits
        LIMITS = {"ASH_COATED_OSMIUM": 20, "INTARIAN_PEPPER_ROOT": 20}
        
        # Memory for trend tracking
        if state.traderData:
            try:
                data = json.loads(state.traderData)
            except:
                data = {"PEPPER_SIGNAL": 0}
        else:
            data = {"PEPPER_SIGNAL": 0}

        for product in state.order_depths:
            depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            curr_pos = state.position.get(product, 0)
            limit = LIMITS.get(product, 20)

            # 1. Get Best Prices and Volumes
            best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
            best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
            
            if not best_ask or not best_bid: continue

            # 2. Calculate Order Book Imbalance (The "Pressure" Signal)
            bid_vol = sum(depth.buy_orders.values())
            ask_vol = sum(abs(v) for v in depth.sell_orders.values())
            imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol) # Range -1 to 1

            # 3. Define Fair Value with Predictive Bias
            # If imbalance is positive (more buyers), we nudge fair value UP
            mid_price = (best_ask + best_bid) / 2
            if product == "ASH_COATED_OSMIUM":
                fair_value = 10000 + (imbalance * 0.5) # Very stable, tiny nudge
            else:
                fair_value = mid_price + (imbalance * 1.5) # Volatile, stronger nudge

            # 4. AGGRESSIVE TAKING (Snipe mispriced orders)
            # Sell to buyers if price is above our predictive fair value
            for price, vol in sorted(depth.buy_orders.items(), key=lambda x: x[0], reverse=True):
                if price > fair_value and curr_pos > -limit:
                    sell_qty = min(vol, curr_pos + limit)
                    orders.append(Order(product, price, -sell_qty))
                    curr_pos -= sell_qty

            # Buy from sellers if price is below our predictive fair value
            for price, vol in sorted(depth.sell_orders.items(), key=lambda x: x[0]):
                if price < fair_value and curr_pos < limit:
                    buy_qty = min(abs(vol), limit - curr_pos)
                    orders.append(Order(product, price, buy_qty))
                    curr_pos += buy_qty

            # 5. STRATEGIC MAKING (Place Limit Orders)
            # Adjust target prices based on current position (Inventory Risk)
            # If pos is +10, we lower both buy and sell prices to encourage selling
            inventory_shift = -2 * (curr_pos / limit) 
            
            target_buy = int(round(fair_value - 1 + inventory_shift))
            target_sell = int(round(fair_value + 1 + inventory_shift))

            # Limit Buy
            if curr_pos < limit:
                # Never buy higher than the current best bid unless the signal is huge
                buy_price = min(target_buy, best_bid + (1 if imbalance > 0.3 else 0))
                orders.append(Order(product, int(buy_price), limit - curr_pos))

            # Limit Sell
            if curr_pos > -limit:
                # Never sell lower than current best ask unless signal is huge
                sell_price = max(target_sell, best_ask - (1 if imbalance < -0.3 else 0))
                orders.append(Order(product, int(sell_price), -(curr_pos + limit)))

            result[product] = orders

        return result, 0, json.dumps(data)