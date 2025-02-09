import matplotlib.pyplot as plt

LSTMloss = [0.532, 0.323, 0.32, 0.332, 0.247, 0.218, 0.164, 0.157]
LSTMacc = [0.722, 0.778, 0.813, 0.797, 0.859, 0.878, 0.879, 0.917]

plt.figure(figsize=(10, 5))
plt.plot(LSTMloss, label='Loss')
plt.plot(LSTMacc, label='Accuracy')
plt.xlabel('Epoch')
plt.title('GRU')
plt.legend()
plt.show()