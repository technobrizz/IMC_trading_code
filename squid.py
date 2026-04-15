from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json
import math

class Trader:
    def run(self, state: TradingState):
        result = {}
        LIMITS = {"ASH_COATED_OSMIUM": 20, "INTARIAN_PEPPER_ROOT": 20}
        
        # Persistent memory for Squid Ink (History and Volatility)
        if state.traderData:
            try:
                data = json.loads(state.traderData)
            except:
                data = {"HISTORY": {}, "VOLATILITY": {}}
        else:
            data = {"HISTORY": {}, "VOLATILITY": {}}

        for product in state.order_depths:
            depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            curr_pos = state.position.get(product, 0)
            limit = LIMITS[product]

            # 1. Get Market Prices
            best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
            best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
            if not best_ask or not best_bid: continue

            # 2. Calculate Micro-Price (The True Current)
            # We weight the price by the volume available at the bid and ask
            bid_vol = depth.buy_orders[best_bid]
            ask_vol = abs(depth.sell_orders[best_ask])
            micro_price = (best_bid * ask_vol + best_ask * bid_vol) / (bid_vol + ask_vol)

            # 3. Dynamic Volatility Adjustment (The Ink)
            if product not in data["HISTORY"]:
                data["HISTORY"][product] = [micro_price]
                volatility = 1.0
            else:
                data["HISTORY"][product].append(micro_price)
                if len(data["HISTORY"][product]) > 10:
                    data["HISTORY"][product].pop(0)
                
                # Simple Volatility (Difference between high and low in the window)
                volatility = max(data["HISTORY"][product]) - min(data["HISTORY"][product])

            # 4. Define Fair Value & Targeted Spread
            # We want a wider spread when volatility is high to stay safe
            fair_value = micro_price
            # Base spread of 2 ticks, plus 10% of the current volatility
            spread_buffer = 1 + (volatility * 0.1)

            # 5. Position Shading (Inventory Risk)
            # If we are long (+), we want to lower our prices to sell
            inventory_skew = (curr_pos / limit) * (spread_buffer * 0.5)

            # 6. MARKET TAKING (Cleaning the Book)
            # Snipe orders that are significantly outside our volatility-adjusted fair value
            for price, vol in sorted(depth.sell_orders.items()):
                if price < (fair_value - spread_buffer) and curr_pos < limit:
                    qty = min(abs(vol), limit - curr_pos)
                    orders.append(Order(product, price, qty))
                    curr_pos += qty

            for price, vol in sorted(depth.buy_orders.items(), reverse=True):
                if price > (fair_value + spread_buffer) and curr_pos > -limit:
                    qty = min(vol, curr_pos + limit)
                    orders.append(Order(product, price, -qty))
                    curr_pos -= qty

            # 7. MARKET MAKING (The Squid Trap)
            # Place orders at the edge of the volatility buffer
            if curr_pos < limit:
                # Place buy order just inside the best bid, but below our fair value
                buy_price = int(min(best_bid + 1, fair_value - spread_buffer - inventory_skew))
                orders.append(Order(product, buy_price, limit - curr_pos))

            if curr_pos > -limit:
                # Place sell order just inside the best ask, but above our fair value
                sell_price = int(max(best_ask - 1, fair_value + spread_buffer - inventory_skew))
                orders.append(Order(product, sell_price, -(curr_pos + limit)))

            result[product] = orders

        return result, 0, json.dumps(data)