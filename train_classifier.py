import json

import torch

from ai import data, train, validate_classifier
from ai.model import Model
from api.config import Config
from api.riot_api import RiotAPIClient
from api.meta_database import Database

SEED = 2132412

def set_global_seed(seed, set_cuda_deterministic=False):
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        if set_cuda_deterministic:
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False

def main():
    set_global_seed(SEED)

    config = Config()

    database_client = Database(config)

    riot_api = RiotAPIClient(config)

    game_data, labels = data.load_train_data(database_client, riot_api, config.ai_input_dim)

    train_x, train_y, val_x, val_y = data.shuffle_and_split_data(game_data, labels, config.ai_validation_split, SEED)

    print(f"Loaded {len(train_x)} training examples & {len(val_x)} validation examples.")

    dataloader_train = data.create_dataloader(train_x, train_y, config.ai_batch_size)
    dataloader_val = data.create_dataloader(val_x, val_y, config.ai_batch_size)

    dataloader_dict = {"train": dataloader_train, "val": dataloader_val}

    device = torch.device('cuda')

    model = Model(config)
    model.to(device)
    model.load()
    criterion = model.get_criterion()
    optimizer = model.get_optimizer()

    # try:
    #     train.train_loop(model, criterion, optimizer, dataloader_dict, device, config.ai_epochs)
    # except KeyboardInterrupt:
    #     pass
    # finally:
    #     model.save()

    validate_classifier.validate(model, game_data, labels, database_client, riot_api, config)

if __name__ == "__main__":
    main()
