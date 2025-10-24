import torch

def train_step(x, y, model, criterion, optim, device, phase):
    examples = len(x)
    x = x.to(device)
    y = y.to(device)

    optim.zero_grad()
    torch.set_grad_enabled(phase == "train")
    out_prob = model(x)

    loss = criterion(out_prob, y)
    if phase == "train":
        loss.backward()
        optim.step()

    preds = out_prob.detach().clone()

    preds[preds >= 0.5] = 1
    preds[preds < 0.5] = 0

    total_loss = loss.item() * examples
    total_acc = torch.sum(preds == y).item()

    return total_loss, out_prob, total_acc

def train_loop(model, criterion, optim, dataloaders, device, epochs):
    val_accuracy = 0

    for epoch in range(1, epochs+1):
        print(f"===== EPOCH {epoch} =====")
        for phase in ("train", "val"):
            if phase == "train":
                model.train()
            else:
                model.eval()

            running_loss, running_corrects, num_examples = 0.0, 0.0, 0

            for x, y in dataloaders[phase]:
                examples = len(x)

                loss, _, acc = train_step(x, y, model, criterion, optim, device, phase)

                if phase == "train":
                    running_loss += loss

                running_corrects += acc
                num_examples += examples

            accuracy = 0 if num_examples == 0 else running_corrects / num_examples
            if phase == "train":
                print(f'|--> train loss: {running_loss / num_examples:.4f}')
            else:
                val_accuracy = accuracy
            print(f'|--> {phase} accuracy: {accuracy:.4f}')

    return val_accuracy

def train_online(model, data, game_won):
    x = torch.tensor(data).float().unsqueeze(0)
    y = torch.tensor([int(game_won)]).float().unsqueeze(0)

    criterion = model.get_criterion()
    optimizer = model.get_optimizer()
    device = torch.device("cpu")

    return train_step(x, y, model, criterion, optimizer, device, "train")
