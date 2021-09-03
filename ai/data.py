import json
from glob import glob

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

from api import game_stats

class GameData(Dataset):
    def __init__(self, data, labels):
        super().__init__()
        self.data = [torch.tensor(x).float() for x in data]
        self.labels = torch.tensor(labels).float().unsqueeze(1)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return self.data[idx], self.labels[idx]

def create_input_mappings(database, riot_api):
    users_map = {user[0]: index for (index, user) in enumerate(database.summoners)}
    champs_map = riot_api.champ_ids

    return users_map, champs_map

def shape_predict_data(database, riot_api, config, users_in_game):
    users_map, champs_map = create_input_mappings(database, riot_api)
    data_vector = np.zeros(config.ai_input_dim)

    for user_data in users_in_game:
        user_index = users_map[user_data[0]]
        champ_index = champs_map[user_data[-1]]
        data_vector[user_index][champ_index] = 1

    return np.array(data_vector)

def load_train_data(database, riot_api, input_dim):
    data_folder = "resources/data"

    users_map, champs_map = create_input_mappings(database, riot_api)

    data_x = []
    data_y = []

    files = glob(f"{data_folder}/*.json")
    for game_file in files:
        with open(game_file, "r", encoding="utf-8") as fp:
            game_data = json.load(fp)

        filtered_data = game_stats.get_filtered_stats(
            database.summoners, database.summoners, game_data
        )[0]

        # Data vector is 25 (users) x 170 (champions)
        data_vector = np.zeros(input_dim)

        for disc_id, stats in filtered_data:
            user_index = users_map[disc_id]
            champ_index = champs_map[stats["championId"]]
            data_vector[user_index, champ_index] = 1

        data_x.append(data_vector)
        data_y.append(int(filtered_data[0][1]["gameWon"]))

    return np.array(data_x), np.array(data_y)

def shuffle_and_split_data(data, labels, validation_split, seed):
    split_point = int(len(data) * validation_split)

    rng = np.random.default_rng(seed)
    rng.shuffle(data)
    train_x = data[:split_point]
    test_x = data[split_point:]

    rng = np.random.default_rng(seed)
    rng.shuffle(labels)
    train_y = labels[:split_point]
    test_y = labels[split_point:]

    return train_x, train_y, test_x, test_y

def create_dataloader(data, labels, batch_size, train=True):
    dataset = GameData(data, labels)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=train,
        drop_last=False
    )
