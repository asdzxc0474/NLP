# -*- coding: utf-8 -*-
"""main.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1QDTA_VobLU2arEG3BvLmQhTuY6HnSv80

# LSTM-arithmetic

## Dataset
- [Arithmetic dataset](https://drive.google.com/file/d/1cMuL3hF9jefka9RyF4gEBIGGeFGZYHE-/view?usp=sharing)
"""

# ! pip install seaborn
# ! pip install -U scikit-learn

import numpy as np
import pandas as pd
import torch
import torch.nn
import torch.nn.utils.rnn
import torch.utils.data
import matplotlib.pyplot as plt
import seaborn as sns
import opencc
import os
from sklearn.model_selection import train_test_split

df_train = pd.read_csv(os.path.join('arithmetic_train.csv'))
df_eval = pd.read_csv(os.path.join('arithmetic_eval.csv'))
df_train.head()

# transform the input data to string
df_train['tgt'] = df_train['tgt'].apply(lambda x: str(x))
df_train['src'] = df_train['src'].add(df_train['tgt'])
df_train['len'] = df_train['src'].apply(lambda x: len(x))

df_eval['tgt'] = df_eval['tgt'].apply(lambda x: str(x))
df_eval['src'] = df_eval['src'].add(df_eval['tgt'])
df_eval['len'] = df_eval['src'].apply(lambda x: len(x))

"""# Build Dictionary
 - The model cannot perform calculations directly with plain text.
 - Convert all text (numbers/symbols) into numerical representations.
 - Special tokens
    - '&lt;pad&gt;'
        - Each sentence within a batch may have different lengths.
        - The length is padded with '&lt;pad&gt;' to match the longest sentence in the batch.
    - '&lt;eos&gt;'
        - Specifies the end of the generated sequence.
        - Without '&lt;eos&gt;', the model will not know when to stop generating.
"""

char_to_id = {
    "0"  : 0,
    "1"  : 1,
    "2"  : 2,
    "3"  : 3,
    "4"  : 4,
    "5"  : 5,
    "6"  : 6,
    "7"  : 7,
    "8"  : 8,
    "9"  : 9,
    "<pad>": 10,
    "<eos>": 11,
    "+"  : 12,
    "-"  : 13,
    "*"  : 14,
    "("  : 15,
    ")"  : 16,
    "="  : 17,
    }
id_to_char = {
    0  : "0",
    1  : "1",
    2  : "2",
    3  : "3",
    4  : "4",
    5  : "5",
    6  : "6",
    7  : "7",
    8  : "8",
    9  : "9",
    10  : "<pad>",
    11  : "<eos>",
    12  : "+",
    13  : "-",
    14  : "*",
    15  : "(",
    16  : ")",
    17  : "=",
}

# write your code here
# Build a dictionary and give every token in the train dataset an id
# The dictionary should contain <eos> and <pad>
# char_to_id is to conver charactors to ids, while id_to_char is the opposite

vocab_size = len(char_to_id)
print('Vocab size{}'.format(vocab_size))

"""# Data Preprocessing
 - The data is processed into the format required for the model's input and output.
 - Example: 1+2-3=0
     - Model input: 1 + 2 - 3 = 0
     - Model output: / / / / / 0 &lt;eos&gt;  (the '/' can be replaced with &lt;pad&gt;)
     - The key for the model's output is that the model does not need to predict the next character of the previous part. What matters is that once the model sees '=', it should start generating the answer, which is '0'. After generating the answer, it should also generate&lt;eos&gt;

"""

def convert_to_id(equation):
    return [char_to_id[char] for char in equation]+ [char_to_id["<eos>"]]

def convert_to_char(equation):
    return [id_to_char[char] for char in equation]+ [char_to_id[11]]

def label_id_list(equation):
    parts = equation.split('=')
    rhs = parts[1]
    pad_list = [char_to_id['<pad>']] * (len(parts[0])+1)
    rhs_ids = [char_to_id[char] for char in rhs]
    label_ids = pad_list + rhs_ids
    return label_ids + [char_to_id["<eos>"]]

def label_id_list_shift(equation):
    equation.pop(0)
    equation.append(char_to_id['<pad>'])
    return equation

df_train['len'] = df_train['src'].apply(len)
df_train['char_id_list'] = df_train['src'].apply(convert_to_id)
df_train['label_id_list'] = df_train['src'].apply(label_id_list)
df_train.head()

df_eval['len'] = df_eval['src'].apply(len)
df_eval['char_id_list'] = df_eval['src'].apply(convert_to_id)
df_eval['label_id_list'] = df_eval['src'].apply(label_id_list)
df_eval.head()

df_train['label_id_list'] = df_train['label_id_list'].apply(label_id_list_shift)
df_eval['label_id_list'] = df_eval['label_id_list'].apply(label_id_list_shift)
df_eval.head()

"""# Hyper Parameters

|Hyperparameter|Meaning|Value|
|-|-|-|
|`batch_size`|Number of data samples in a single batch|64|
|`epochs`|Total number of epochs to train|10|
|`embed_dim`|Dimension of the word embeddings|256|
|`hidden_dim`|Dimension of the hidden state in each timestep of the LSTM|256|
|`lr`|Learning Rate|0.001|
|`grad_clip`|To prevent gradient explosion in RNNs, restrict the gradient range|1|
"""

batch_size = 1024
epochs = 8
embed_dim = 256
hidden_dim = 256
lr = 0.001
grad_clip = 1

"""# Data Batching
- Use `torch.utils.data.Dataset` to create a data generation tool called  `dataset`.
- The, use `torch.utils.data.DataLoader` to randomly sample from the `dataset` and group the samples into batches.
"""

import torch
class Dataset(torch.utils.data.Dataset):
    def __init__(self, sequences):
        self.sequences = sequences

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, index):
        # Extract the input data x and the ground truth y from the data
        sequence = self.sequences.iloc[index]

        x = sequence['char_id_list']
        y = sequence['label_id_list']

        return x, y

# collate function, used to build dataloader
def collate_fn(batch):
    batch_x = [torch.tensor(data[0]) for data in batch]
    batch_y = [torch.tensor(data[1]) for data in batch]
    batch_x_lens = torch.LongTensor([len(x) for x in batch_x])
    batch_y_lens = torch.LongTensor([len(y) for y in batch_y])

    # Pad the input sequence
    pad_batch_x = torch.nn.utils.rnn.pad_sequence(batch_x,
                                                  batch_first=True,
                                                  padding_value=char_to_id['<pad>'])

    pad_batch_y = torch.nn.utils.rnn.pad_sequence(batch_y,
                                                  batch_first=True,
                                                  padding_value=char_to_id['<pad>'])
    return pad_batch_x, pad_batch_y, batch_x_lens, batch_y_lens

ds_train = Dataset(df_train[['char_id_list', 'label_id_list']])
ds_eval = Dataset(df_eval[['char_id_list', 'label_id_list']])

from torch.utils.data import DataLoader
# Build dataloader of train set and eval set, collate_fn is the collate function
dl_train = DataLoader(dataset=ds_train, batch_size= batch_size, shuffle= True, collate_fn = collate_fn)
dl_eval = DataLoader(dataset=ds_eval, batch_size= batch_size, shuffle= False, collate_fn=collate_fn)

first_batch = next(iter(dl_train))
batch_x, batch_y, batch_x_lens, batch_y_lens = first_batch

# 印出資料
print("Inputs (batch_x):", batch_x[1])
print("Labels (batch_y):", batch_y[1])
print("Input lengths (batch_x_lens):", batch_x_lens[1])
print("Label lengths (batch_y_lens):", batch_y_lens[1])

"""# Model Design

## Execution Flow
1. Convert all characters in the sentence into embeddings.
2. Pass the embeddings through an LSTM sequentially.
3. The output of the LSTM is passed into another LSTM, and additional layers can be added.
4. The output from all time steps of the final LSTM is passed through a Fully Connected layer.
5. The character corresponding to the maximum value across all output dimensions is selected as the next character.

## Loss Function
Since this is a classification task, Cross Entropy is used as the loss function.

## Gradient Update
Adam algorithm is used for gradient updates.
"""

class CharRNN(torch.nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim):
        super(CharRNN, self).__init__()

        self.embedding = torch.nn.Embedding(num_embeddings=vocab_size,
                                            embedding_dim=embed_dim,
                                            padding_idx=char_to_id['<pad>'])

        self.rnn_layer1 = torch.nn.GRU(input_size=embed_dim,
                                        hidden_size=hidden_dim,
                                        batch_first=True)

        self.rnn_layer2 = torch.nn.GRU(input_size=hidden_dim,
                                        hidden_size=hidden_dim,
                                        batch_first=True)

        self.linear = torch.nn.Sequential(torch.nn.Linear(in_features=hidden_dim,
                                                          out_features=hidden_dim),
                                          torch.nn.ReLU(),
                                          torch.nn.Linear(in_features=hidden_dim,
                                                          out_features=vocab_size))

    def forward(self, batch_x, batch_x_lens):
        return self.encoder(batch_x, batch_x_lens)

    # The forward pass of the model
    def encoder(self, batch_x, batch_x_lens):
        batch_x = self.embedding(batch_x)

        batch_x = torch.nn.utils.rnn.pack_padded_sequence(batch_x,batch_x_lens,batch_first=True,enforce_sorted=False)

        batch_x, _ = self.rnn_layer1(batch_x)
        batch_x, _ = self.rnn_layer2(batch_x)

        batch_x, _ = torch.nn.utils.rnn.pad_packed_sequence(batch_x,batch_first=True)

        batch_x = self.linear(batch_x)

        return batch_x

    def generator(self, start_char, max_len=200):
        # Initialize char_list with the token ids for the start_char sequence
        char_list = [char_to_id[c] for c in start_char]
        next_char = None
        # We will iterate to predict the next characters
        while len(char_list) < max_len:
            # Write your code here
            # Pack the char_list to tensor
            # Input the tensor to the embedding layer, LSTM layers, linear respectively

            current_seq = torch.tensor(char_list).unsqueeze(0).to(next(self.parameters()).device)
            current_seq_emb = self.embedding(current_seq)
            output, _ = self.rnn_layer1(current_seq_emb)
            output, _ = self.rnn_layer2(output)
            logits = self.linear(output)
            y = logits[:, -1, :]
            next_char = torch.argmax(y, dim=-1).item() # Obtain the next token prediction y
            print(next_char)
            if next_char == char_to_id['<eos>']:
                break
            char_list.append(next_char)
        return [id_to_char[ch_id] for ch_id in char_list]

torch.manual_seed(2)


device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

model = CharRNN(vocab_size,
                embed_dim,
                hidden_dim)

criterion = torch.nn.CrossEntropyLoss(ignore_index=char_to_id['<pad>'])
optimizer = torch.optim.AdamW(model.parameters(), lr=0.001)

"""# Training
1. The outer `for` loop controls the `epoch`
    1. The inner `for` loop uses `data_loader` to retrieve batches.
        1. Pass the batch to the `model` for training.
        2. Compare the predicted results `batch_pred_y` with the true labels `batch_y` using Cross Entropy to calculate the loss `loss`
        3. Use `loss.backward` to automatically compute the gradients.
        4. Use `torch.nn.utils.clip_grad_value_` to limit the gradient values between `-grad_clip` &lt; and &lt; `grad_clip`.
        5. Use `optimizer.step()` to update the model (backpropagation).
2.  After every `1000` batches, output the current loss to monitor whether it is converging.
"""

from tqdm import tqdm
from copy import deepcopy
model = model.to(device)
i = 0
for epoch in range(1, epochs+1):
    model.train()
    # The process bar
    bar = tqdm(dl_train, desc=f"Train epoch {epoch}")
    for batch_x, batch_y, batch_x_lens, batch_y_lens in bar:
        optimizer.zero_grad()
        # Write your code here
        # Clear the gradient

        batch_pred_y = model(batch_x.to(device), batch_x_lens)
        loss = criterion(batch_pred_y.view(-1, vocab_size), batch_y.to(device).view(-1))
        loss.backward()

        # Write your code here
        # Input the prediction and ground truths to loss function
        # Back propagation

        torch.nn.utils.clip_grad_value_(model.parameters(), grad_clip)
        optimizer.step()

        # Write your code here
        # Optimize parameters in the model
        i+=1
        if i%50==0:
            bar.set_postfix(loss = loss.item())

    # Evaluate your model
    model.eval()
    bar = tqdm(dl_eval, desc=f"Validation epoch {epoch}")
    matched = 0
    total = 0
    for batch_x, batch_y, batch_x_lens, batch_y_lens in bar:
        batch_y = batch_y.to(device)
        predictions = model(batch_x.to(device), batch_x_lens)# Write your code here. Input the batch_x to the model and generate the predictions
        pred_tokens = predictions.argmax(dim=-1)
        for i in range(pred_tokens.size(0)):
            mask = (batch_y[i] != char_to_id['<pad>']) & (batch_y[i] != char_to_id['<eos>'])
            filtered_preds = pred_tokens[i][mask]
            filtered_labels = batch_y[i][mask]
            matched += (filtered_preds == filtered_labels).sum().item()
            total += filtered_labels.numel()  # Only count valid tokens for total

        # for i in range(pred_tokens.size(0)):
        #   print(pred_tokens[0],"ccccc\n",batch_y[0])
        #   if torch.equal(pred_tokens[i], batch_y[i]):
        #     matched += 1
        #   total += 1


        # for i in range(pred_tokens.size(0)):
        #     for j in range(len(pred_tokens[i])):
        #         if pred_tokens[i][j] != char_to_id['<eos>'] or pred_tokens[i][j] != char_to_id['<pad>']:
        #             total += 1
        #             if pred_tokens[i][j] == batch_y[i][j]:
        #                 matched += 1
    print(f"Exact Match: {matched / total}")
        # Write your code here.
        # Check whether the prediction match the ground truths
        # Compute exact match (EM) on the eval dataset
        # EM = correct/total

torch.save(model, 'LSTM.pt')

"""# Generation
Use `model.generator` and provide an initial character to automatically generate a sequence.
"""

model = model.to("cpu")
print("".join(model.generator('22+12=')))

