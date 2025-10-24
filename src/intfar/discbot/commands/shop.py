from datetime import datetime

from intfar.api import util as api_util
from intfar.discbot.commands.base import *

def format_item_list(items: List[Tuple[str, int, int]], headers: Tuple[str]) -> List[str]:
    strings = []
    max_len_1 = 0
    max_len_2 = 0
    for item_details in items:
        item_name = item_details[0]
        quantity = item_details[-1]
        if len(item_details) > 2:
            price = item_details[1]

        name_fmt = f"{item_name}"
        if len(name_fmt) > max_len_1:
            max_len_1 = len(name_fmt)

        price_fmt = None
        if len(item_details) > 2:
            price_fmt = f"\t{api_util.format_tokens_amount(price)} GBP"
            if len(price_fmt) > max_len_2:
                max_len_2 = len(price_fmt)

        quant_fmt = f"\t{quantity}x"
        strings.append((name_fmt, price_fmt, quant_fmt))

    h_1 = headers[0]
    header_len_1 = max_len_1
    if len(headers) > 2:
        header_len_1 = int(max_len_1 * 1.5)
    pad_h_1 = " " * ((header_len_1 - 1) - len(h_1))
    h_2 = headers[1]
    pad_h_2 = ""
    h_3 = ""
    if len(headers) > 2:
        pad_h_2 = " " * ((max_len_2 // 2 + 4) - len(h_2))
        h_3 = headers[2]

    header_str = f"{h_1} {pad_h_1}{h_2} {pad_h_2}{h_3}"
    list_fmt = header_str + "\n"
    list_fmt += "-" * len(header_str) + "\n"

    for item_str, price_str, quantity_str in strings:
        pad_1 = ""
        pad_2 = ""
        if len(item_str) < max_len_1:
            pad_1 = " " * (max_len_1 - len(item_str))
        if price_str is None:
            price_str = ""
        elif len(price_str) < max_len_2:
            pad_2 = " " * (max_len_2 - len(price_str))

        list_fmt += f"{item_str}{pad_1}{price_str}{pad_2}{quantity_str}\n"

    return list_fmt

class ShopCommand(Command):
    NAME = "shop"
    DESCRIPTION = (
        "Get a list of totally real items that you " +
        "can buy with your hard-earned betting tokens!"
    )

    async def handle(self):
        if not self.client.shop_handler.shop_is_open():
            response = "Shop is closed! It may open again later, who knows."
            await self.message.channel.send(response)
            return

        items = self.client.meta_database.get_items_in_shop()

        dt_now = datetime.now()
        time_to_closing = api_util.format_duration(dt_now, self.client.shop_handler.shop_closing_dt)

        response = f"Shop closes in {time_to_closing}!\n"
        response += "Items in the shop:\n```"
        response += format_item_list(items, ("Item Name", "Price", "Quantity"))
        response += "```"

        await self.message.channel.send(response)

class BuyCommand(Command):
    NAME = "buy"
    DESCRIPTION = (
        "Buy one or more copies of an item from the shop at a " +
        "given price (or cheapest if no price is given)."
    )
    ACCESS_LEVEL = "self"
    MANDATORY_PARAMS = [CommandParam("quantity"), CommandParam("item")]

    async def handle(self, quantity: int, item: str):
        if not self.client.shop_handler.shop_is_open():
            response = "Shop is closed! Buying stuff is not possible."
            await self.message.channel.send(response)
            return

        response = self.client.shop_handler.buy_item(
            self.message.author.id, item, quantity
        )[1]

        await self.message.channel.send(response)

class SellCommand(Command):
    NAME = "sell"
    DESCRIPTION = "Add a listing in the shop for one or more copies of an item that you own."
    ACCESS_LEVEL = "all"
    MANDATORY_PARAMS = [CommandParam("quantity"), CommandParam("item"), CommandParam("price")]

    async def handle(self, quantity: int, item: str, price: int):
        if not self.client.shop_handler.shop_is_open():
            response = "Shop is closed! Selling stuff is not possible."
            await self.message.channel.send(response)
            return

        response = self.client.shop_handler.sell_item(
            self.message.author.id, item, price, quantity
        )[1]

        await self.message.channel.send(response)

class CancelSellCommand(Command):
    NAME = "cancel_sell"
    DESCRIPTION = (
        "Cancel a listing in the shop that you made for " +
        "the given number of items at the given price"
    )
    ACCESS_LEVEL = "self"
    MANDATORY_PARAMS = [CommandParam("quantity"), CommandParam("item"), CommandParam("price")]

    async def handle(self, quantity: int, item: str, price: int):
        if not self.client.shop_handler.shop_is_open():
            response = "Shop is closed! Cancelling a listing is not possible."
            await self.message.channel.send(response)
            return

        response = self.client.shop_handler.cancel_listing(
            self.message.author.id, item, price, quantity
        )[1]

        await self.message.channel.send(response)

class InventoryCommand(Command):
    NAME = "inventory"
    DESCRIPTION = "List all the items that your or someone else owns."
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = [TargetParam("person")]

    async def handle(self, target_id: int):
        items = self.client.meta_database.get_items_for_user(target_id)
        target_name = self.client.get_discord_nick(target_id, self.message.guild.id)
        if items == []:
            response = f"{target_name} currently owns no items."
        else:
            response = f"Items owned by {target_name}:\n```"
            response += format_item_list(items, ("Item Name", "Quantity"))
            response += "```"

        await self.message.channel.send(response)
