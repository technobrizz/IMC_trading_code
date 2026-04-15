from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json

class Trader:
    def run(self, state: TradingState):
        result = {}
        # Maximum allowed positions
        LIMITS = {"ASH_COATED_OSMIUM": 20, "INTARIAN_PEPPER_ROOT": 20}
        
        # Load state/EMA values from previous turns
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
            limit = LIMITS[product]

            # 1. Get Best Market Prices
            best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
            best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
            if not best_ask or not best_bid: continue
            
            # 2. Adaptive Fair Value Calculation
            # We use an EMA to track the "true" price without being anchored to 10k
            mid_price = (best_ask + best_bid) / 2
            if product not in data["EMA"]:
                data["EMA"][product] = mid_price
            else:
                # 0.4 weight on new price makes it very responsive
                data["EMA"][product] = (0.4 * mid_price) + (0.6 * data["EMA"][product])
            
            fair_value = data["EMA"][product]

            # 3. AGGRESSIVE MARKET TAKING (All Levels)
            # Scan all sell orders and buy everything below fair value
            sorted_asks = sorted(depth.sell_orders.items())
            for price, vol in sorted_asks:
                if price < fair_value and curr_pos < limit:
                    buy_qty = min(abs(vol), limit - curr_pos)
                    orders.append(Order(product, price, buy_qty))
                    curr_pos += buy_qty

            # Scan all buy orders and sell everything above fair value
            sorted_bids = sorted(depth.buy_orders.items(), reverse=True)
            for price, vol in sorted_bids:
                if price > fair_value and curr_pos > -limit:
                    sell_qty = min(vol, curr_pos + limit)
                    orders.append(Order(product, price, -sell_qty))
                    curr_pos -= sell_qty

            # 4. MARKET MAKING (The "Resin" Pennying)
            # If we still have room in our position, place limit orders to capture the spread
            
            # Inventory shading: if we are long, we want to sell more/buy less
            # We adjust our 'pennying' target based on how close we are to the limit
            buy_offset = 1 if curr_pos < 10 else 2
            sell_offset = 1 if curr_pos > -10 else 2

            if curr_pos < limit:
                # Place buy at best bid + 1, capped by fair value - 1
                our_buy_price = min(best_bid + 1, int(fair_value - buy_offset))
                orders.append(Order(product, our_buy_price, limit - curr_pos))

            if curr_pos > -limit:
                # Place sell at best ask - 1, floored by fair value + 1
                our_sell_price = max(best_ask - 1, int(fair_value + sell_offset))
                orders.append(Order(product, our_sell_price, -(curr_pos + limit)))

            result[product] = orders

        return result, 0, json.dumps(data)