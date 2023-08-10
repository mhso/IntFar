class User(dict):
    def __init__(self, ingame_name: list[str], ingame_id: list[str], **extra_params):
        self.__setitem__("ingame_name", ingame_name)
        self.__setitem__("ingame_id", ingame_id)

        for param in extra_params:
            setattr(self, param, extra_params[param])
            self.__setitem__(param, extra_params[param])

    @property
    def ingame_name(self) -> list[str]:
        return self.__getitem__("ingame_name")

    @property
    def ingame_id(self) -> list[str]:
        return self.__getitem__("ingame_id")
