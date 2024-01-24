from api.game_database import GameDatabase

class CS2GameDatabase(GameDatabase):
    @property
    def game_user_params(self):
        return ["match_auth_code", "latest_match_token"]

    def set_new_cs2_sharecode(self, disc_id, steam_id, sharecode):
        query = f"UPDATE users SET latest_match_token=? WHERE disc_id=? AND ingame_id=?"

        with self:
            self.execute_query(query, sharecode, disc_id, steam_id)
            for index, ingame_id in enumerate(self.game_users[disc_id].ingame_id):
                if ingame_id == steam_id:
                    self.game_users[disc_id].latest_match_token[index] = sharecode
                    break
