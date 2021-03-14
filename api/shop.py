from datetime import datetime
from api.util import parse_amount_str, format_tokens_amount, format_duration

def get_shop_error_msg(msg, event):
    event_desc = "Listing" if event == "sell" else "Purchase"
    return f"{event_desc} of item failed: {msg}"

class ShopHandler:
    def __init__(self, config, database):
        self.config = config
        self.database = database
        self.shop_closing_dt = datetime(2021, 4, 1, 12, 0, 0)
        if self.shop_is_open():
            dt_now = datetime.now()
            time_to_closing = format_duration(dt_now, self.shop_closing_dt)
            self.config.log(f"Shop closes in {time_to_closing}.")

    def shop_is_open(self):
        if not self.config.shop_open:
            return False

        dt_now = datetime.now()
        if dt_now.timestamp() > self.shop_closing_dt.timestamp():
            self.config.log("The shop is now closed!")
            self.config.shop_open = False

        return self.config.shop_open

    def buy_item(self, disc_id, item_name, quantity_str="1"):
        item_split = item_name.split(" ")
        price = None
        try:
            price = parse_amount_str(item_split[-1])
            item_name = " ".join(item_split[:-1])
        except ValueError:
            pass

        try:
            quantity = int(quantity_str)
        except ValueError:
            err_msg = get_shop_error_msg(f"Invalid quantity: '{quantity_str}'.", "buy")
            return (False, err_msg)

        if not self.database.item_exists(item_name):
            err_msg = f"No item named **{item_name}** exists in the shop."
            return (False, err_msg)

        items = self.database.get_items_matching_price(item_name, price, quantity)

        if len(items) < quantity: # Not enough copies in the shop.
            if items == []:
                quantity_desc = "No"
            else:
                quantity_desc = f"Only {len(items)}"
            err_msg = f"{quantity_desc} copies of **{item_name}** in the shop "
            if price is not None:
                err_msg += f"matching a price of {price} GBP "
            err_msg += f"(you wanted to buy {quantity} copies)."

            return (False, err_msg)

        total_price = 0 # Sum up the total price of all copies of 'item_name'.
        for item in items:
            total_price += item[1]

        copy_identifier = "copy" if quantity == 1 else "copies"
        if self.database.get_token_balance(disc_id) < total_price:
            err_msg = (
                f"You do not have enough GBP to buy {quantity} {copy_identifier} " +
                f"of **{item_name}**"
            )
            return (False, err_msg)

        self.database.buy_item(disc_id, items, total_price, item_name)

        tokens_name = self.config.betting_tokens

        status_msg = (
            f"You just bought {quantity} {copy_identifier} of **{item_name}** " +
            f"for a total price of {format_tokens_amount(total_price)} {tokens_name}!"
        )

        return (True, status_msg)

    def sell_item(self, disc_id, item_name, price_str, quantity_str="1"):
        try:
            price = None if price_str is None else parse_amount_str(price_str)
        except ValueError:
            err_msg = get_shop_error_msg(f"Invalid token amount: '{price_str}'.", "sell")
            return (False, err_msg)

        if price < 1 or price > self.config.max_shop_price:
            fmt_max_price = format_tokens_amount(self.config.max_shop_price)
            err_msg = get_shop_error_msg(
                f"Invalid price (must be above 0 and below {fmt_max_price}).", "sell"
            )
            return (False, err_msg)

        try:
            quantity = int(quantity_str)
        except ValueError:
            err_msg = get_shop_error_msg(f"Invalid quantity: '{quantity_str}'.", "sell")
            return (False, err_msg)

        if quantity < 1:
            err_msg = get_shop_error_msg("Quantity to sell must be more than zero", "sell")
            return (False, err_msg)

        items = self.database.get_matching_items_for_user(disc_id, item_name, quantity)

        if len(items) < quantity:
            if items == []:
                quantity_desc = "don't own any copy"
            elif len(items) == 1:
                quantity_desc = "only own 1 copy"
            else:
                quantity_desc = f"only own {len(items)} copies"

            err_msg = get_shop_error_msg(
                f"You {quantity_desc} of **{item_name}**.", "sell"
            )
            return (False, err_msg)

        self.database.sell_item(disc_id, items, item_name, price)

        copy_identifier = "copy" if quantity == 1 else "copies"
        tokens_name = self.config.betting_tokens
        status_msg = (
            f"You just listed {quantity} {copy_identifier} "
            f"of **{item_name}** at {format_tokens_amount(price)} {tokens_name}"
        )
        if quantity > 1:
            status_msg += " each"
        status_msg += "!"

        return (True, status_msg)
