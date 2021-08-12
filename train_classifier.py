import json

import torch

from ai import data, train, validate_classifier
from ai.model import Model
from api.config import Config
from api.riot_api import APIClient
from api.database import Database

def main():
    auth = json.load(open("discbot/auth.json"))

    config = Config()
    config.env = auth["env"]

    config.discord_token = auth["discordToken"]
    config.riot_key = auth["riotDevKey"] if config.use_dev_token else auth["riotAPIKey"]

    database_client = Database(config)

    riot_api = APIClient(config)

    game_data, labels = data.load_train_data(database_client, riot_api, config.ai_input_dim)

    train_x, train_y, val_x, val_y = data.shuffle_and_split_data(game_data, labels, config.ai_validation_split)

    print(f"Loaded {len(train_x)} training examples & {len(val_x)} validation examples.")

    dataloader_train = data.create_dataloader(train_x, train_y, config.ai_batch_size)
    dataloader_val = data.create_dataloader(val_x, val_y, config.ai_batch_size)

    dataloader_dict = {"train": dataloader_train, "val": dataloader_val}

    device = torch.device('cuda')

    model = Model(config)
    model.to(device)
    criterion = model.get_criterion()
    optimizer = model.get_optimizer()

    try:
        train.train_loop(model, criterion, optimizer, dataloader_dict, device, config.ai_epochs)
    except KeyboardInterrupt:
        pass
    finally:
        model.save()
        model.to(torch.device("cpu"))

        validate_classifier.validate(model, database_client, riot_api, config)

if __name__ == "__main__":
    main()
