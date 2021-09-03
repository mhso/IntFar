class Command:
    def __init__(self, command, description, mandatory_params=None, optional_params=None):
        self.cmd = command
        self.desc = description
        self.mandatory_params = mandatory_params
        self.optional_params = optional_params

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
