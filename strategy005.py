from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json

class Trader:
    def run(self, state: TradingState):
        result = {}
        LIMITS = {"ASH_COATED_OSMIUM": 20, "INTARIAN_PEPPER_ROOT": 20}
        
        # EMA Smoothing Factor (Alpha). Higher = faster reaction to price changes
        # 0.2 means 20% weight to newest price, 80% to history.
        ALPHA = 0.2 

        if state.traderData:
            try:
                data = json.loads(state.traderData)
            except:
                data = {"EMA": {}}
        else:
            data = {"EMA": {}}

        for product in state.order_depths:
            depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            curr_pos = state.position.get(product, 0)
            limit = LIMITS.get(product, 20)

            # 1. Get Market Prices
            best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
            best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
            
            if not best_ask or not best_bid: continue
            mid_price = (best_ask + best_bid) / 2

            # 2. Update Exponential Moving Average (Fair Value)
            if product not in data["EMA"]:
                data["EMA"][product] = mid_price
            else:
                data["EMA"][product] = (ALPHA * mid_price) + (1 - ALPHA) * data["EMA"][product]
            
            fair_value = data["EMA"][product]

            # 3. Aggressive Market Taking (Sniping)
            # If someone is selling way below our fair value, buy it all instantly.
            for price, vol in sorted(depth.sell_orders.items()):
                if price < fair_value - 1 and curr_pos < limit:
                    buy_qty = min(abs(vol), limit - curr_pos)
                    orders.append(Order(product, price, buy_qty))
                    curr_pos += buy_qty

            # If someone is buying way above our fair value, sell to them instantly.
            for price, vol in sorted(depth.buy_orders.items(), reverse=True):
                if price > fair_value + 1 and curr_pos > -limit:
                    sell_qty = min(vol, curr_pos + limit)
                    orders.append(Order(product, price, -sell_qty))
                    curr_pos -= sell_qty

            # 4. Market Making (Pennying the Spread)
            # If we aren't at our position limits, try to be the best price in the book.
            
            # Place a Buy Order just above the current best bid
            if curr_pos < limit:
                # We want to buy at best_bid + 1, but never above our fair value
                our_buy_price = min(best_bid + 1, int(fair_value - 1))
                # Adjust for inventory: if we have too much, bid even lower
                if curr_pos > 10: our_buy_price -= 1 
                
                orders.append(Order(product, our_buy_price, limit - curr_pos))

            # Place a Sell Order just below the current best ask
            if curr_pos > -limit:
                # We want to sell at best_ask - 1, but never below our fair value
                our_sell_price = max(best_ask - 1, int(fair_value + 1))
                # Adjust for inventory: if we are short, ask even higher
                if curr_pos < -10: our_sell_price += 1
                
                orders.append(Order(product, our_sell_price, -(curr_pos + limit)))

            result[product] = orders

        return result, 0, json.dumps(data)