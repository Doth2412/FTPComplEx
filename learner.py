# Copyright (c) Facebook, Inc. and its affiliates.

import argparse
from typing import Dict
import logging
import torch
from torch import optim
import sys

from datasets import TemporalDataset
from optimizers import TKBCOptimizer, IKBCOptimizer
from models import ComplEx, TComplEx, TPComplEx, TNTComplEx, FTPComplEx
from regularizers import N3, Lambda3

parser = argparse.ArgumentParser(
    description="Temporal ComplEx"
)
parser.add_argument(
    '--dataset',default='ICEWS14' , type=str,
    help="Dataset name"
)
models = [
    'ComplEx', 'TComplEx', 'TPComplEx', 'TNTComplEx', 'FTPComplEx',
]
parser.add_argument(
    '--model',default = 'TPComplEx', choices=models,
    help="Model in {}".format(models)
)
parser.add_argument(
    '--max_epochs', default=100, type=int,
    help="Number of epochs."
)
parser.add_argument(
    '--valid_freq', default=10, type=int,
    help="Number of epochs between each valid."
)
parser.add_argument(
    '--rank', default=100, type=int,
    help="Factorization rank."
)
parser.add_argument(
    '--batch_size', default=1000, type=int,
    help="Batch size."
)
parser.add_argument(
    '--learning_rate', default=1e-1, type=float,
    help="Learning rate"
)
parser.add_argument(
    '--emb_reg', default=0., type=float,
    help="Embedding regularizer strength"
)
parser.add_argument(
    '--time_reg', default=0., type=float,
    help="Timestamp regularizer strength"
)
parser.add_argument(
    '--no_time_emb', default=False, action="store_true",
    help="Use a specific embedding for non temporal relations"
)

parser.add_argument(
    '--alpha', default = 1.0, type = float,
    help = "Temporal 2 ratio"
)

parser.add_argument(
    '--beta', default = 1.0, type = float,
    help = "Temporal 3 ratio"
)



parser.add_argument('-test', '--do_test', action='store_true') #action='store_true'
parser.add_argument('-save', '--do_save', action='store_true')
parser.add_argument('-id', '--model_id', type=str, default='0')

args = parser.parse_args()

model_path = './logs/' + args.model + '_' + args.dataset  + '_' + args.model_id

dataset = TemporalDataset(args.dataset)

sizes = dataset.get_shape()
model = {
    'ComplEx': ComplEx(sizes, args.rank),
    'TComplEx': TComplEx(sizes, args.rank, no_time_emb=args.no_time_emb),
    'TNTComplEx': TNTComplEx(sizes, args.rank, no_time_emb=args.no_time_emb),
    'TPComplEx': TPComplEx(sizes, args.rank, no_time_emb=args.no_time_emb),
    'FTPComplEx': FTPComplEx(sizes, args.rank, no_time_emb=args.no_time_emb, a = args.alpha, b = args.beta),
}[args.model]
model = model.cuda()


opt = optim.Adagrad(model.parameters(), lr=args.learning_rate)


emb_reg = N3(args.emb_reg)
time_reg = Lambda3(args.time_reg)


if args.do_test:

    def avg_both(mrrs: Dict[str, float], hits: Dict[str, torch.FloatTensor]):
        """
        aggregate metrics for missing lhs and rhs
        :param mrrs: d
        :param hits:
        :return:
        """
        m = (mrrs['lhs'] + mrrs['rhs']) / 2.
        h = (hits['lhs'] + hits['rhs']) / 2.
        return {'MRR': m, 'hits@[1,3,10]': h}


    model_dict=torch.load(model_path)
    valid, test, train = [
                avg_both(*dataset.eval(model_dict, split, -1 if split != 'train' else 50000))
                for split in ['valid', 'test', 'train']
            ]
    print("valid: ", valid)
    print("test: ", test)
    print("train: ", train) 
    sys.exit(0)

for epoch in range(args.max_epochs):
    examples = torch.from_numpy(
        dataset.get_train().astype('int64')
    )

    model.train()
    if dataset.has_intervals():
        optimizer = IKBCOptimizer(
            model, emb_reg, time_reg, opt, dataset,
            batch_size=args.batch_size
        )
        optimizer.epoch(examples)

    else:
        optimizer = TKBCOptimizer(
            model, emb_reg, time_reg, opt,
            batch_size=args.batch_size
        )
        optimizer.epoch(examples)


    def avg_both(mrrs: Dict[str, float], hits: Dict[str, torch.FloatTensor]):
        """
        aggregate metrics for missing lhs and rhs
        :param mrrs: d
        :param hits:
        :return:
        """
        m = (mrrs['lhs'] + mrrs['rhs']) / 2.
        h = (hits['lhs'] + hits['rhs']) / 2.
        return {'MRR': m, 'hits@[1,3,10]': h}

    if epoch < 0 or (epoch + 1) % args.valid_freq == 0:
        if dataset.has_intervals():
            valid, test, train = [
                dataset.eval(model, split, -1 if split != 'train' else 50000)
                for split in ['valid', 'test', 'train']
            ]
            print("valid: ", valid)
            print("test: ", test)
            print("train: ", train)
            

        else:
            valid, test, train = [
                avg_both(*dataset.eval(model, split, -1 if split != 'train' else 50000))
                for split in ['valid', 'test', 'train']
            ]
            print("valid: ", valid)
            print("test: ", test)
            print("train: ", train)
        if args.do_save:
            torch.save(model, model_path)

