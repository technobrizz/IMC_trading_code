from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json

class Trader:
    def run(self, state: TradingState):
        result = {}
        LIMITS = {"ASH_COATED_OSMIUM": 20, "INTARIAN_PEPPER_ROOT": 20}
        
        # Memory to store the previous mid-prices for trend detection
        if state.traderData:
            try:
                data = json.loads(state.traderData)
            except:
                data = {"PREV_MID": {}}
        else:
            data = {"PREV_MID": {}}

        for product in state.order_depths:
            depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            curr_pos = state.position.get(product, 0)
            limit = LIMITS[product]

            # 1. Identify Best Bid and Ask
            best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
            best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
            if not best_ask or not best_bid: continue

            # 2. Kelp Signal: Volume-Weighted Fair Value (Micro-price)
            # This predicts where the price is going based on order book pressure
            bid_vol = depth.buy_orders[best_bid]
            ask_vol = abs(depth.sell_orders[best_ask])
            
            # Micro-price calculation
            fair_value = (best_bid * ask_vol + best_ask * bid_vol) / (bid_vol + ask_vol)

            # 3. Trend Adjustment
            # If the price is moving fast, we shift our fair value to catch the trend
            prev_mid = data["PREV_MID"].get(product, fair_value)
            price_change = fair_value - prev_mid
            fair_value += price_change * 0.5 # Anticipate the next move
            data["PREV_MID"][product] = fair_value

            # 4. Aggressive Liquidity Snatching
            # Take existing orders that are better than our predictive fair value
            for price, vol in sorted(depth.sell_orders.items()):
                if price <= fair_value - 1 and curr_pos < limit:
                    qty = min(abs(vol), limit - curr_pos)
                    orders.append(Order(product, price, qty))
                    curr_pos += qty

            for price, vol in sorted(depth.buy_orders.items(), reverse=True):
                if price >= fair_value + 1 and curr_pos > -limit:
                    qty = min(vol, curr_pos + limit)
                    orders.append(Order(product, price, -qty))
                    curr_pos -= qty

            # 5. Kelp Market Making (Pennying with Position Skew)
            # We want to be the best price (+1/-1) but we skew based on position
            # If we are long (pos > 0), we lower our prices to encourage selling.
            pos_skew = (curr_pos / limit) * 2.0 
            
            if curr_pos < limit:
                # Target bid is 1 tick above best bid, capped by fair value minus skew
                bid_price = int(min(best_bid + 1, fair_value - 1 - pos_skew))
                orders.append(Order(product, bid_price, limit - curr_pos))

            if curr_pos > -limit:
                # Target ask is 1 tick below best ask, floored by fair value plus skew
                ask_price = int(max(best_ask - 1, fair_value + 1 - pos_skew))
                orders.append(Order(product, ask_price, -(curr_pos + limit)))

            result[product] = orders

        return result, 0, json.dumps(data)