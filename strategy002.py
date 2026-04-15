from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json

class Trader:
    def run(self, state: TradingState):
        result = {}
        POSITION_LIMITS = {"ASH_COATED_OSMIUM": 20, "INTARIAN_PEPPER_ROOT": 20}
        
        # Load or initialize history
        if state.traderData:
            try:
                data = json.loads(state.traderData)
            except:
                data = {"PEPPER_HISTORY": [], "OSMIUM_HISTORY": []}
        else:
            data = {"PEPPER_HISTORY": [], "OSMIUM_HISTORY": []}

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            current_pos = state.position.get(product, 0)
            limit = POSITION_LIMITS.get(product, 20)

            # 1. Calculate Fair Value
            best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
            best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
            
            if best_ask is None or best_bid is None: continue
            mid_price = (best_ask + best_bid) / 2

            if product == "ASH_COATED_OSMIUM":
                # Slightly dynamic fair value around 10k anchor
                data["OSMIUM_HISTORY"].append(mid_price)
                if len(data["OSMIUM_HISTORY"]) > 5: data["OSMIUM_HISTORY"].pop(0)
                fair_value = 10000 
            else:
                data["PEPPER_HISTORY"].append(mid_price)
                if len(data["PEPPER_HISTORY"]) > 10: data["PEPPER_HISTORY"].pop(0)
                fair_value = sum(data["PEPPER_HISTORY"]) / len(data["PEPPER_HISTORY"])

            # 2. Market Making with Inventory Shading
            # If we are "long" (pos > 0), we want to sell more than buy.
            # We shift our target prices down.
            inventory_bias = -1 * (current_pos / limit) # -1.0 to +1.0
            
            # Define our buy and sell targets around fair value
            # We want to buy at fair - 1 and sell at fair + 1
            buy_price = int(round(fair_value - 1 + inventory_bias))
            sell_price = int(round(fair_value + 1 + inventory_bias))

            # 3. Liquidity Taking (Take profitable existing orders)
            # Buy existing sells cheaper than our buy_price
            for price, vol in sorted(order_depth.sell_orders.items()):
                if price <= buy_price and current_pos < limit:
                    buy_amount = min(abs(vol), limit - current_pos)
                    orders.append(Order(product, price, buy_amount))
                    current_pos += buy_amount

            # Sell to existing buys higher than our sell_price
            for price, vol in sorted(order_depth.buy_orders.items(), reverse=True):
                if price >= sell_price and current_pos > -limit:
                    sell_amount = min(vol, current_pos + limit)
                    orders.append(Order(product, price, -sell_amount))
                    current_pos -= sell_amount

            # 4. Market Making (Place our own orders to be the best bid/ask)
            # If we still have room in our position limit, place limit orders
            if current_pos < limit:
                # Place a buy order at the best possible price that is still profitable
                final_buy_price = min(buy_price, best_bid + 1)
                orders.append(Order(product, final_buy_price, limit - current_pos))
            
            if current_pos > -limit:
                # Place a sell order at the best possible price
                final_sell_price = max(sell_price, best_ask - 1)
                orders.append(Order(product, final_sell_price, -(current_pos + limit)))

            result[product] = orders

        return result, 0, json.dumps(data)