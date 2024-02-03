from datetime import datetime

import api.util as api_util

def format_item_list(items, headers):
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

async def handle_shop_msg(client, message):
    if not client.shop_handler.shop_is_open():
        response = "Shop is closed! It may open again later, who knows."
        await message.channel.send(response)
        return

    items = client.meta_database.get_items_in_shop()

    dt_now = datetime.now()
    time_to_closing = api_util.format_duration(dt_now, client.shop_handler.shop_closing_dt)

    response = f"Shop closes in {time_to_closing}!\n"
    response += "Items in the shop:\n```"
    response += format_item_list(items, ("Item Name", "Price", "Quantity"))
    response += "```"

    await message.channel.send(response)

async def handle_buy_msg(client, message, quantity, item):
    if not client.shop_handler.shop_is_open():
        response = "Shop is closed! Buying stuff is not possible."
        await message.channel.send(response)
        return

    response = client.shop_handler.buy_item(
        message.author.id, item, quantity
    )[1]

    await message.channel.send(response)

async def handle_sell_msg(client, message, quantity, item, price):
    if not client.shop_handler.shop_is_open():
        response = "Shop is closed! Selling stuff is not possible."
        await message.channel.send(response)
        return

    response = client.shop_handler.sell_item(
        message.author.id, item, price, quantity
    )[1]

    await message.channel.send(response)

async def handle_cancel_sell_msg(client, message, quantity, item, price):
    if not client.shop_handler.shop_is_open():
        response = "Shop is closed! Cancelling a listing is not possible."
        await message.channel.send(response)
        return

    response = client.shop_handler.cancel_listing(
        message.author.id, item, price, quantity
    )[1]

    await message.channel.send(response)

async def handle_inventory_msg(client, message, target_id):
    items = client.meta_database.get_items_for_user(target_id)
    target_name = client.get_discord_nick(target_id, message.guild.id)
    if items == []:
        response = f"{target_name} currently owns no items."
    else:
        response = f"Items owned by {target_name}:\n```"
        response += format_item_list(items, ("Item Name", "Quantity"))
        response += "```"

    await message.channel.send(response)
