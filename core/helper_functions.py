from __future__ import print_function, division, absolute_import
import torch
import math
import torch.nn as nn
from torch.autograd import Variable


def to_var(x, volatile=False, requires_grad=False):
    if torch.cuda.is_available():
        x = x.cuda()
    return Variable(x, volatile=volatile, requires_grad=requires_grad)


def state_func(configs):
    '''
    state_configs = {
                        'num_classes': num_classes,
                        'labels': labels,
                        'inputs': inputs,
                        'student': student,
                        'current_iter': i_tau,
                        'max_iter': max_t,
                        'train_loss_history': training_loss_history,
                        'val_loss_history': val_loss_history
                    }
    '''
    num_classes = configs['num_classes']
    labels = configs['labels']
    inputs = configs['inputs']
    student = configs['student']
    current_iter = configs['current_iter']
    max_iter = configs['max_iter']
    train_loss_history = configs['train_loss_history']
    val_loss_history = configs['val_loss_history']

    _inputs = {'inputs':inputs, 'labels':labels}

    predicts, _ = student(_inputs, None) # predicts are logits

    predicts = nn.LogSoftmax()(predicts)
    predicts = torch.exp(predicts)

    n_samples = inputs.size(0)
    data_features = to_var(torch.zeros(n_samples, num_classes))
    data_features[range(n_samples), labels.data] = 1

    # def sigmoid(x):
    #     return 1.0/(1.0 + math.exp(-x))
    def normalize_loss(loss):
        return loss/2.3
    # [ max_iter; averaged_train_loss; best_val_loss ]
    model_features = to_var(torch.zeros(n_samples, 3))
    model_features[:, 0] = current_iter / max_iter  # current iteration number
    model_features[:, 1] = min(1.0, 1.0 if len(train_loss_history) == 0 else sum(train_loss_history)/len(train_loss_history)/2.3)
    # sigmoid(sum(train_loss_history)/len(train_loss_history)) # averaged training loss
    model_features[:, 2] = min(1.0, 1.0 if len(val_loss_history) == 0 else min(val_loss_history)/2.3)
    # sigmoid(min(val_loss_history))

    combined_features = to_var(torch.zeros(n_samples, 12))
    combined_features[:, :10] = predicts

    eps = 1e-6
    combined_features[:, 10:11] = -torch.log(predicts[range(n_samples), labels.data] + eps)

    mask = to_var(torch.ones(n_samples, num_classes))

    mask[range(n_samples), labels.data] = 0
    combined_features[:, 11:12] = predicts[range(n_samples), labels.data] - torch.max(mask*predicts, 1)[0]

    states = torch.cat([data_features, model_features, combined_features], 1)
    return states


def evaluator(predicts, labels):
    labels = labels.squeeze()
    criterion = nn.CrossEntropyLoss()
    _, predicted = torch.max(predicts.data, 1)
    num_correct = predicted.eq(labels.data).cpu().sum() #torch.sum(torch.max(predicts, 1)[1] == labels).cpu().data[0]
    num_samples = predicts.size(0)
    loss = criterion(predicts, labels)
    # print ('num_correct:', num_correct, 'num_samples:', num_samples)
    return {'num_correct': num_correct, 'num_samples':num_samples, 'loss':loss}