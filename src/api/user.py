class User(dict):
    def __init__(
        self,
        disc_id: int,
        secret: str = None,
        player_name: list[str] = None,
        player_id: list[str] = None,
        main = True,
        default_game = None,
        **extra_params
    ):
        all_params = {
            "disc_id": disc_id,
            "secret": secret,
            "player_name": player_name,
            "player_id": player_id,
            "main": main,
            "default_game": default_game
        }
        all_params.update(extra_params)

        for param in all_params:
            setattr(self, param, all_params[param])
            self.__setitem__(param, all_params[param])

    @staticmethod
    def clone(user):
        return User(**user)
