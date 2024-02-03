from ai import data

# Dave (Kayle), Murt (Nunu), Nø (Draven), Me (Yone), Mads (Lux)
GAME_DATA_4 = [
    (115142485579137029, None, None, 10),
    (172757468814770176, None, None, 20),
    (347489125877809155, None, None, 119),
    (267401734513491969, None, None, 777),
    (331082926475182081, None, None, 99)
]

# Dave (Senna), Murt (Viego), Thomas (Lillia), Me (Yasuo), Mads (Maokai)
GAME_DATA_5 = [
    (115142485579137029, None, None, 235),
    (172757468814770176, None, None, 234),
    (219497453374668815, None, None, 876),
    (267401734513491969, None, None, 157),
    (331082926475182081, None, None, 57)
]

# Dave (Senna), Murt (Viego), Thomas (Lillia), Me (Yasuo), Mads (Xerath)
GAME_DATA_6 = [
    (115142485579137029, None, None, 235),
    (172757468814770176, None, None, 234),
    (219497453374668815, None, None, 876),
    (267401734513491969, None, None, 157),
    (331082926475182081, None, None, 101)
]

# Dave (Senna), Murt (Viego), Thomas (Xin), Me (Yasuo), Mads (Xerath)
GAME_DATA_7 = [
    (115142485579137029, None, None, 235),
    (172757468814770176, None, None, 234),
    (219497453374668815, None, None, 5),
    (267401734513491969, None, None, 157),
    (331082926475182081, None, None, 101)
]

# Dave (Nami), Murt (Viego), Thomas (Xin), Me (Yasuo), Mads (Xerath)
GAME_DATA_8 = [
    (115142485579137029, None, None, 267),
    (172757468814770176, None, None, 234),
    (219497453374668815, None, None, 5),
    (267401734513491969, None, None, 157),
    (331082926475182081, None, None, 101)
]

# Dave (Viego), Murt (Tahm), Thomas (Xin), Me (Yasuo), Mads (Xerath)
GAME_DATA_9 = [
    (115142485579137029, None, None, 234),
    (172757468814770176, None, None, 223),
    (219497453374668815, None, None, 5),
    (267401734513491969, None, None, 157),
    (331082926475182081, None, None, 101)
]

# Dave (Viego), Murt (Tahm), Thomas (Xin), Me (Jhin), Mads (Xerath)
GAME_DATA_10 = [
    (115142485579137029, None, None, 234),
    (172757468814770176, None, None, 223),
    (219497453374668815, None, None, 5),
    (267401734513491969, None, None, 202),
    (331082926475182081, None, None, 101)
]

# Game data ranked from theoretical worst to best
ALL_TEST_EXAMPLES = [
    GAME_DATA_4, GAME_DATA_5,
    GAME_DATA_6, GAME_DATA_7, GAME_DATA_8, GAME_DATA_9, GAME_DATA_10
]

def get_win_ratio(user_data, data_x, data_y, users_map, champs_map):
    disc_id = user_data[0]
    user_index = users_map[disc_id]
    champ_id = user_data[-1]
    champ_index = champs_map[champ_id]

    win_count = 0
    games = 0

    for data_matrix, label in zip(data_x, data_y):
        if data_matrix[user_index, champ_index] == 1:
            win_count += label
            games += 1

    return win_count / games

def validate(model, data_x, data_y, database, riot_api, config):
    users_map, champs_map = data.create_input_mappings(database, riot_api)

    total_deviation = 0

    for index, user_data in enumerate(ALL_TEST_EXAMPLES):
        shaped_data = data.shape_predict_data(database, riot_api, config, user_data)
        win_probability = model.predict(shaped_data)

        avg_ratio = 0

        for user_info in user_data:
            avg_ratio += get_win_ratio(user_info, data_x, data_y, users_map, champs_map)

        avg_ratio = avg_ratio / 5

        total_deviation += abs(win_probability - avg_ratio)

        print(f"Example #{index+1} - Probability: {win_probability:.4f} - Avg Ratio: {avg_ratio:.4f}")

    print(f"Average Deviation: {total_deviation / len(ALL_TEST_EXAMPLES):.4f}")
