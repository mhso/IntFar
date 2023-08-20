class User(dict):
    def __init__(self, disc_id, secret: str, ingame_name: list[str]=None, ingame_id: list[str]=None, **extra_params):
        self.__setitem__("disc_id", disc_id)
        self.__setitem__("secret", secret)
        self.__setitem__("ingame_name", ingame_name)
        self.__setitem__("ingame_id", ingame_id)

        for param in extra_params:
            setattr(self, param, extra_params[param])
            self.__setitem__(param, extra_params[param])

    @property
    def secret(self) -> str:
        return self.__getitem__("secret")

    @property
    def main(self) -> bool:
        return self.__getitem__("disc_id")

    @property
    def ingame_name(self) -> list[str]:
        return self.__getitem__("ingame_name")

    @property
    def ingame_id(self) -> list[str]:
        return self.__getitem__("ingame_id")
