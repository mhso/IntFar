import torch

from ai.train import train_online

MODEL_SAVE_PATH = "resources/ai_model.pt"

class Model(torch.nn.Module):
    def __init__(self, config):
        super().__init__()

        self.config = config

        self.conv_1 = torch.nn.Conv1d(
            config.ai_input_dim[0], config.ai_conv_filters,
            config.ai_conv_kernel, config.ai_conv_stride
        )
        self.batch_norm_1 = torch.nn.BatchNorm1d(config.ai_conv_filters)

        self.pool_1 = torch.nn.AvgPool1d(2, 2)

        self.conv_2 = torch.nn.Conv1d(
            config.ai_conv_filters, config.ai_conv_filters * 2,
            config.ai_conv_kernel, config.ai_conv_stride
        )
        self.batch_norm_2 = torch.nn.BatchNorm1d(config.ai_conv_filters * 2)

        self.pool_2 = torch.nn.AvgPool1d(2, 2)

        use_pool = True
        divisor = 16 if use_pool else 4

        cls_in = (config.ai_input_dim[1] // divisor) * (config.ai_conv_filters * 2)

        self.classifier = torch.nn.Sequential(
            torch.nn.Dropout(config.ai_dropout),
            torch.nn.Linear(cls_in, config.ai_hidden_dim),
            torch.nn.Dropout(config.ai_dropout * 0.5),
            torch.nn.Linear(config.ai_hidden_dim, config.ai_output_dim)
        )

        self.init_weights()

    def forward(self, x):
        x = self.conv_1(x)
        x = self.batch_norm_1(x)
        x = self.pool_1(x)

        x = self.conv_2(x)
        x = self.batch_norm_2(x)
        x = self.pool_2(x)

        x = x.reshape(x.shape[0], -1)

        return self.classifier(x)

    def predict(self, data):
        self.eval()
        torch.set_grad_enabled(False)

        x = torch.tensor(data).float().unsqueeze(0)

        device_name = "cpu"# if self.config.env == "production" else "cuda"
        device = torch.device(device_name)

        x = x.to(device)

        out_prob = torch.sigmoid(self(x).squeeze())

        return out_prob

    def init_weights(self):
        init_range = self.config.ai_init_range
        for conv_module in (self.conv_1, self.conv_2):
            conv_module.weight.data.uniform_(-init_range, init_range)

        for i in range(len(self.classifier)):
            module = self.classifier[i]
            if isinstance(module, torch.nn.Linear):
                module.bias.data.zero_()
                module.weight.data.uniform_(-init_range, init_range)

    def get_optimizer(self):
        return torch.optim.Adam(
            self.parameters(), self.config.ai_learning_rate,
            weight_decay=self.config.ai_weight_decay
        )

    def get_criterion(self):
        return torch.nn.MSELoss()

    def save(self):
        torch.save(self.state_dict(), MODEL_SAVE_PATH)

    def load(self):
        self.load_state_dict(torch.load(MODEL_SAVE_PATH, map_location=torch.device("cpu")))
        self.eval()
        self.config.log("Prediction Classifier Loaded")

def run_loop(config, bot_pipe):
    ai_model = Model(config)
    ai_model.load()
    try:
        while True:
            action, data = bot_pipe.recv()
            if action == "predict":
                output = ai_model.predict(data[0])
                bot_pipe.send(output)
            elif action == "train":
                loss, probability, _ = train_online(ai_model, data[0], data[1])
                probability = torch.sigmoid(probability.squeeze())
                ai_model.save()
                bot_pipe.send((loss, probability.item()))
    except (BrokenPipeError, KeyboardInterrupt):
        pass
