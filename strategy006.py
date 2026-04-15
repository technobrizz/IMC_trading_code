from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json

class Trader:
    def run(self, state: TradingState):
        result = {}
        LIMITS = {"ASH_COATED_OSMIUM": 20, "INTARIAN_PEPPER_ROOT": 20}
        
        # Load memory for Pepper Root (which is less stable than Osmium)
        if state.traderData:
            try:
                data = json.loads(state.traderData)
            except:
                data = {"PEPPER_EMA": None}
        else:
            data = {"PEPPER_EMA": None}

        for product in state.order_depths:
            depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            curr_pos = state.position.get(product, 0)
            limit = LIMITS[product]

            # 1. Determine Fair Value
            best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
            best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
            if not best_ask or not best_bid: continue
            mid_price = (best_ask + best_bid) / 2

            if product == "ASH_COATED_OSMIUM":
                # Rainforest Resin logic: 10,000 is the gravity well
                fair_value = 10000 
            else:
                # For Pepper, use a fast-adapting fair value (EMA)
                if data["PEPPER_EMA"] is None:
                    data["PEPPER_EMA"] = mid_price
                else:
                    data["PEPPER_EMA"] = 0.3 * mid_price + 0.7 * data["PEPPER_EMA"]
                fair_value = data["PEPPER_EMA"]

            # 2. MARKET TAKING (Immediate Snipe)
            # Take any sell orders < fair value
            for price, vol in sorted(depth.sell_orders.items()):
                if price < fair_value and curr_pos < limit:
                    take_qty = min(abs(vol), limit - curr_pos)
                    orders.append(Order(product, price, take_qty))
                    curr_pos += take_qty

            # Take any buy orders > fair value
            for price, vol in sorted(depth.buy_orders.items(), reverse=True):
                if price > fair_value and curr_pos > -limit:
                    take_qty = min(vol, curr_pos + limit)
                    orders.append(Order(product, price, -take_qty))
                    curr_pos -= take_qty

            # 3. MARKET MAKING (Pennying the Spread)
            # Calculate how much we 'shade' our price based on position
            # Higher position = lower prices (willing to sell cheaper)
            shading = -1 * (curr_pos / 5) # Moves price by 1-4 ticks at limits

            # Place our Bid (Buy Limit Order)
            if curr_pos < limit:
                # We want to be 1 tick above the market, but never above fair value
                bid_price = int(min(best_bid + 1, fair_value - 1 + shading))
                orders.append(Order(product, bid_price, limit - curr_pos))

            # Place our Ask (Sell Limit Order)
            if curr_pos > -limit:
                # We want to be 1 tick below the market, but never below fair value
                ask_price = int(max(best_ask - 1, fair_value + 1 + shading))
                orders.append(Order(product, ask_price, -(curr_pos + limit)))

            result[product] = orders

        return result, 0, json.dumps(data)