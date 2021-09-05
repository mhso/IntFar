async def handle_kick_msg(client, message, target_id):
    target_name = client.get_discord_nick(target_id, message.guild.id)

    response = f"{target_name} has been kicked from Int-Far "
    response += "for being a bad boi!\nHis data will be WIPED "
    response += "and he will forever live in shame {emote_im_nat_kda_player_yo}"

    await message.channel.send(client.insert_emotes(response))
