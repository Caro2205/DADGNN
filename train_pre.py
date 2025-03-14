import torch
from model_pre import Model
from data_helper import DataHelper
import numpy as np
import tqdm
import sys, random
import argparse
import time, datetime
import os
import warnings
import wandb

warnings.filterwarnings("ignore")
NUM_ITER_EVAL = 100
EARLY_STOP_EPOCH = 10

# to run this
# source dadgnn_env/bin/activate
# swap OUT of dadgnn folder
# python3 DADGNN/train_pre.py --dataset sst2 --wandb True

logs_folder = 'bert_results_high_p/sst2_sweep'

os.makedirs(logs_folder, exist_ok=True)

###### parameter tuning stuff
sweep_configuration = {
    "method": "bayes",
    "name": "sweep",
    "metric": {"goal": "maximize", "name": "val_acc"},
    "parameters": {
        "dropout": {"values": [0.3, 0.5]},
        "k": {"values": [4, 5, 6]},
        #"wd": {"values": [1e-05, 1e-07, 1e-09]},
        "ngram": {"values": [4, 5]}
    }
}

sweep_id = wandb.sweep(sweep=sweep_configuration, project="my-first-sweep")
#################################################


def get_time_dif(start_time):
    end_time = time.time()
    time_dif = end_time - start_time
    return datetime.timedelta(seconds=int(round(time_dif)))

def log_to_file(filename, message):
    safe_filename = filename.replace(":", "-").replace(" ", "_")
    with open(f'DADGNN/{logs_folder}/{safe_filename}', "a") as file: 
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file.write(f"[{timestamp}] {message}\n")
    print(f"Logged to {safe_filename}: {message}")

def dev(model, dataset, dev_data_helper):
    model.eval()
    total_pred = 0
    correct = 0
    iter = 0
    with torch.no_grad():
      for content, label, _ in dev_data_helper.batch_iter(batch_size=64, num_epoch=1):
          iter += 1

          logits = model(content)
          pred = torch.argmax(logits, dim=1)
          correct_pred = torch.sum(pred == label)
          correct += correct_pred
          total_pred += len(content)

    total_pred = float(total_pred)
    correct = correct.float()
    return torch.div(correct, total_pred)


def test(model, dataset):
    model.cuda()
    data_helper = DataHelper(dataset=dataset, mode='test')
   
    total_pred = 0
    correct = 0
    iter = 0
   
    with torch.no_grad():
      for content, label, _ in data_helper.batch_iter(batch_size=64, num_epoch=1):
        iter += 1
        model.eval()
        logits = model(content)
        pred = torch.argmax(logits, dim=1)

        correct_pred = torch.sum(pred == label)
        correct += correct_pred
        total_pred += len(content)

    total_pred = float(total_pred)
    correct = correct.float()
    return torch.div(correct, total_pred).to('cpu').numpy()


def train(ngram, name, wd, bar, drop_out, num_hidden, num_layers, num_heads, k, alpha, dataset, is_cuda, log_filename, edges=True):

    #parameters_dict.update({
    #'dataset': {
    #    'value': dataset},
    #'num_layers': {
    #    'value': num_layers},
    #'alpha': {
    #    'value': alpha},
    #'trainable_edges': {
    #    'value': edges},
    #'seed': {
    #    'value': args.rand},
    #})
    
    #wandb.init(project=name, config=set_config)
    #print("CONFIGGGG")
    #print(wandb.config)
    #config = wandb.config
    #if config == {}: print('ERROR: Config file is empty.')
    
    #drop_out = config.dropout
    #wd = config.wd
    #num_heads = config["attention_heads"]
    #k = config["k"]
    #num_hidden = config["hidden_layers"]

    print('load data helper.')
    path = 'DADGNN/data/' + dataset + '/' + dataset + '-vocab.txt'
    with open(path,'r') as f:
      vocab = f.read()
      vocab = vocab.split('\n')
    data_helper = DataHelper(dataset=dataset, mode='train', vocab=vocab)
    model = Model(num_hidden, num_layers, num_heads, k, alpha,
                      vocab=data_helper.vocab, n_gram=ngram, drop_out=drop_out, class_num=len(data_helper.labels_str), num_feats=768) #change num_feats here for glove 300 and for bert 768
    
    dev_data_helper = DataHelper(dataset=dataset, mode='dev', vocab=vocab)
    if is_cuda:
        print('cuda')
        model.cuda()

    loss_func = torch.nn.CrossEntropyLoss()
    optim = torch.optim.Adam(model.parameters(), weight_decay=wd)


    iter = 0
    if bar:
        pbar = tqdm.tqdm(total=NUM_ITER_EVAL)
    best_acc = 0.0
    last_best_epoch = 0
    start_time = time.time()
    total_loss = 0.0
    total_correct = 0
    total = 0
    for content, label, epoch in data_helper.batch_iter(batch_size=64, num_epoch=100):
        improved = ''
        model.train()

        logits = model(content)
        loss = loss_func(logits, label)
        pred = torch.argmax(logits, dim=1)

        correct = torch.sum(pred == label)
        total_correct += correct
        total += len(label)
        total_loss += loss.item()

        optim.zero_grad()
        loss.backward()
        optim.step()

        iter += 1
        if bar:
            pbar.update()
        if iter % NUM_ITER_EVAL == 0:
            if bar:
                pbar.close()

            val_acc = test(model, dataset)
            if val_acc > best_acc:
                best_acc = val_acc
                last_best_epoch = epoch
                improved = '*'

                torch.save(model.state_dict(), name + '.pth')

            if epoch - last_best_epoch >= EARLY_STOP_EPOCH:
                return model
            msg = 'Epoch: {0:>6} Iter: {1:>6}, Train Loss: {5:>7.2}, Train Acc: {6:>7.2%}' \
                  + 'Val Acc: {2:>7.2%}, Time: {3}{4}' \
                  # + ' Time: {5} {6}'

            log_to_file(log_filename, f'Iter: {iter}; Validation Accuracy: {val_acc}; Best Accuracy: {best_acc}')

            wandb.log({
                "Iteration": iter,
                "Validation Accuracy": val_acc,
                "Best Accuracy": best_acc,
                "Training Loss": total_loss / NUM_ITER_EVAL,
                "Training Accuracy": float(total_correct) / float(total)
            })

            print(msg.format(epoch, iter, val_acc, get_time_dif(start_time), improved, total_loss/ NUM_ITER_EVAL,
                             float(total_correct) / float(total)))

            total_loss = 0.0
            total_correct = 0
            total = 0
            if bar:
                pbar = tqdm.tqdm(total=NUM_ITER_EVAL)

    return model


#make this to def main() -> get arguments through wandb if set to true, otherwise do the same
# in wandb the use function=main for sweeping
# https://docs.wandb.ai/guides/sweeps/add-w-and-b-to-your-code/
def main():
    run = wandb.init()

    parser = argparse.ArgumentParser()
    parser.add_argument('--ngram', required=False, type=int, default=4, help='ngram number')
    parser.add_argument('--name', required=False, type=str, default='model', help='project name')
    parser.add_argument('--bar', required=False, type=int, default=1, help='show bar')
    parser.add_argument('--wd', required=False, type=float, default=1e-6, help='weight decay')
    parser.add_argument('--dropout', required=False, type=float, default=0.5, help='dropout rate')
    parser.add_argument('--num_hidden', required=False, type=int, default=64, help='hidden dimension')
    parser.add_argument('--num_layers', required=False, type=int, default=5, help='model layer')
    parser.add_argument('--num_heads', required=False, type=int, default=2, help='head number')
    parser.add_argument('--k', required=False, type=int, default=5, help='k')
    parser.add_argument('--alpha', required=False, type=int, default=0.5, help='alpha')
    parser.add_argument('--dataset', required=True, type=str, help='dataset')
    parser.add_argument('--edges', required=False, type=int, default=1, help='trainable edges')
    parser.add_argument('--rand', required=False, type=int, default=42, help='rand_seed')
    parser.add_argument('--wandb', required=False, type=bool, default=False, help='use wandb')

    args = parser.parse_args()

    current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = 'Log_' + str(current_time)

    #log_to_file(log_filename, f'dataset: {args.dataset}; ngram: {args.ngram}; dropout: {args.dropout}; trainable edges: {args.edges}; k: {args.k}')

    print('ngram: %d' % args.ngram)
    print('project_name: %s' % args.name)
    print('dataset: %s' % args.dataset)
    print('trainable_edges: %s' % args.edges)
    
    SEED = args.rand
    torch.manual_seed(SEED)
    torch.cuda.manual_seed(SEED)
    np.random.seed(SEED)
    random.seed(SEED)

    if args.bar == 1:
        bar = True
    else:
        bar = False
    
    if args.edges == 1:
        edges = True
        print('trainable edges')
    else:
        edges = False

    if args.wandb == True:
        #sweep_id = wandb.sweep(sweep=set_config, project="my-first-sweep")
        args.dropout = wandb.config.dropout
        #args.wd = wandb.config.wd
        #args.num_heads = wandb.config.attention_heads
        args.k = wandb.config.k
        #args.num_hidden = wandb.config.hidden_layers
        args.ngram = wandb.config.ngram

    log_to_file(log_filename, f'dataset: {args.dataset}; ngram: {args.ngram}; dropout: {args.dropout}; trainable edges: {args.edges}; k: {args.k}; hidden layers: {args.num_hidden}; attention heads: {args.num_heads}; weight decay: {args.wd}')
    
    model = train(args.ngram, args.name, args.wd, bar, args.dropout, args.num_hidden, args.num_layers, args.num_heads, args.k, args.alpha,dataset=args.dataset, is_cuda=True, edges=edges, log_filename=log_filename)
    model.load_state_dict(torch.load('model.pth'))
    result = test(model, args.dataset)
    print('top-1 test acc: ', result)
    log_to_file(log_filename, 'top-1 test acc: ' + str(result))


wandb.agent(sweep_id, function=main)