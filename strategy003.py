from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json

class Trader:
    def run(self, state: TradingState):
        result = {}
        # Limits for the current products
        LIMITS = {"ASH_COATED_OSMIUM": 20, "INTARIAN_PEPPER_ROOT": 20}
        
        # Persistent memory
        if state.traderData:
            data = json.loads(state.traderData)
        else:
            data = {"PEPPER_HISTORY": []}

        for product in state.order_depths:
            depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            curr_pos = state.position.get(product, 0)
            limit = LIMITS.get(product, 20)

            # 1. Get Market Prices
            best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
            best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
            
            if not best_ask or not best_bid: continue

            # 2. Calculate Micro-Price (Predictive Mid-Price)
            bid_vol = depth.buy_orders[best_bid]
            ask_vol = abs(depth.sell_orders[best_ask])
            micro_price = (best_bid * ask_vol + best_ask * bid_vol) / (bid_vol + ask_vol)

            # 3. Product Specific Fair Value Logic
            if product == "ASH_COATED_OSMIUM":
                # Osmium is mean-reverting. Use a hybrid of 10k and Micro-price
                fair_value = 0.8 * 10000 + 0.2 * micro_price
            else:
                # Pepper Root: Use Micro-price with a small history smoothing
                data["PEPPER_HISTORY"].append(micro_price)
                if len(data["PEPPER_HISTORY"]) > 8: data["PEPPER_HISTORY"].pop(0)
                fair_value = sum(data["PEPPER_HISTORY"]) / len(data["PEPPER_HISTORY"])

            # 4. Market Taking Phase (Aggressive Sniping)
            # Take any sell order significantly below our predictive fair value
            for price, vol in sorted(depth.sell_orders.items()):
                if price <= (fair_value - 0.5) and curr_pos < limit:
                    buy_qty = min(abs(vol), limit - curr_pos)
                    orders.append(Order(product, price, buy_qty))
                    curr_pos += buy_qty

            # Take any buy order significantly above our predictive fair value
            for price, vol in sorted(depth.buy_orders.items(), reverse=True):
                if price >= (fair_value + 0.5) and curr_pos > -limit:
                    sell_qty = min(vol, curr_pos + limit)
                    orders.append(Order(product, price, -sell_qty))
                    curr_pos -= sell_qty

            # 5. Market Making Phase (Smart Pennying)
            # We place orders to catch the spread, skewed by our inventory
            reservation_price = fair_value - 0.1 * (curr_pos / limit)
            
            # Place Buy Limit Order
            if curr_pos < limit:
                # If buy volume is high, we penny more aggressively
                bid_price = min(best_bid + 1, int(reservation_price - 1))
                orders.append(Order(product, int(bid_price), limit - curr_pos))
            
            # Place Sell Limit Order
            if curr_pos > -limit:
                # If sell volume is high, we penny more aggressively
                ask_price = max(best_ask - 1, int(reservation_price + 1))
                orders.append(Order(product, int(ask_price), -(curr_pos + limit)))

            result[product] = orders

        return result, 0, json.dumps(data)