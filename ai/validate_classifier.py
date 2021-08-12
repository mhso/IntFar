from ai import data

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
    GAME_DATA_7, GAME_DATA_8, GAME_DATA_9, GAME_DATA_10
]

def validate(model, database, riot_api, config):
    for index, user_data in enumerate(ALL_TEST_EXAMPLES):
        shaped_data = data.shape_predict_data(database, riot_api, config, user_data)
        win_probability = model.predict(shaped_data)

        print(f"Example #{index+1} - Probability: {win_probability}")
