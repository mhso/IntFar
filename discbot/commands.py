
    async def get_data_and_respond(
        self, handler, message, target_name=None,
        target_all=True, access_level=None, args=None
    ):
        try:
            handler_args = [message]
            if args is not None:
                handler_args.extend(args)

            if target_name is not None:
                target_id = self.get_target_id(
                    message.author.id, message.guild.id, target_name, target_all
                )
                user_is_registered = self.database.user_exists(message.author.id)
                if not user_is_registered:
                    if access_level == "all":
                        await message.channel.send(
                            "You must be registered to Int-Far:tm: to use this command."
                        )
                        return
                    elif access_level == "self" and target_id == message.author.id:
                        await message.channel.send(
                            (
                                "You must be registered to Int-Far:tm: " +
                                "to target yourself with this command."
                            )
                        )
                        return

                handler_args.append(target_id)
            await handler(*handler_args)
        except InvalidArgument as arg_exception:
            await message.channel.send(arg_exception.args[0])
            self.config.log(arg_exception, self.config.log_error)
        except DBException as db_exception:
            response = "Something went wrong when querying the database! "
            response += self.insert_emotes("{emote_fu}")
            await message.channel.send(response)
            self.config.log(db_exception, self.config.log_error)

class Target:
    def __init__(self, value, default="me"):
        self.value = value
        self.default = default

class Parameter:
    def __init__(self, value):
        pass

    def 

class Command:
    def __init__(self, command, description, handler, target_all=True, access_level=None, mandatory_params=None, optional_params=None):
        self.cmd = command
        self.desc = description
        self.handler = handler
        self.target_all = target_all
        self.access_level = access_level
        self.mandatory_params = mandatory_params
        self.optional_params = optional_params

    async def handle_command(client, message):
        handler_args = [message]
        if args is not None:
            handler_args.extend(args)

        if target_name is not None:
            target_id = self.get_target_id(
                message.author.id, message.guild.id, target_name, target_all
            )
            user_is_registered = self.database.user_exists(message.author.id)
            if not user_is_registered:
                if access_level == "all":
                    await message.channel.send(
                        "You must be registered to Int-Far:tm: to use this command."
                    )
                    return
                elif access_level == "self" and target_id == message.author.id:
                    await message.channel.send(
                        (
                            "You must be registered to Int-Far:tm: " +
                            "to target yourself with this command."
                        )
                    )
                    return

            handler_args.append(target_id)
        await handler(*handler_args)
    except InvalidArgument as arg_exception:
        await message.channel.send(arg_exception.args[0])
        self.config.log(arg_exception, self.config.log_error)
    except DBException as db_exception:
        response = "Something went wrong when querying the database! "
        response += self.insert_emotes("{emote_fu}")
        await message.channel.send(response)
        self.config.log(db_exception, self.config.log_error)

    def format_params_list(self, params):
        if params == "mandatory":
            params_list = self.mandatory_params
            l_brace, r_brace = "[", "]"
        else:
            params_list = self.optional_params
            l_brace, r_brace = "(", ")"

        if params_list is None:
            return ""

        return f"{l_brace}" + f"{l_brace} {r_brace}".join(params_list) + f"{r_brace}"

    def __str__(self):
        params_str_1 = self.format_params_list("mandatory")
        params_str_2 = self.format_params_list("optional")
        if params_str_1 != "" and params_str_2 == "":
            params_str_1 = " " + params_str_1

        if params_str_1 != "" and params_str_2 != "":
            params_str_2 = " " + params_str_2
        params_str = f"{params_str_1}{params_str_2}` "
        return f"`!{self.cmd}{params_str}- {self.desc}"

intfar_desc = (
    "Show how many times you (or someone else) has been the Int-Far. " +
    "'!intfar all' lists Int-Far stats for all users."
)
intfar_cmd = Command("intfar", intfar_desc, optional_params=["person"])
print(intfar_cmd)
