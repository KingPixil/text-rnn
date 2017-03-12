import numpy as np
import pickle

def unique(seq):
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]

class RNN(object):
    def __init__(self):
        # Hyperparameters

        # Number of Hidden Layers in Network
        self.hiddenLayers = 100

        # Learning Rate
        self.learning_rate = 1e-2

        # Weights for Hidden Layer to Hidden Layer
        self.WH = np.random.randn(self.hiddenLayers, self.hiddenLayers)*0.01

        # Initial Hidden State
        self.h = {}
        self.prev_h = np.zeros((self.hiddenLayers, 1))

        # Internal Cursor
        self.cursor = 0

    def softmax(self, x, temperature=1.0):
        exp_x = np.exp(x / temperature)
        return exp_x / np.sum(exp_x)

    def loss(self, prediction, targets):
        return -np.log(prediction[targets, 0])

    def forward_step(self, X, prev_h, temperature=1.0):
        # Compute hidden state
        h = np.tanh(np.dot(self.WX, X) + np.dot(self.WH, prev_h) + self.bh)
        # Compute output
        return self.softmax(np.dot(self.WY, h) + self.by), h

    def step(self):
        # Total Loss
        loss = 0

        # Setup Hidden State
        self.h = {}
        self.h[-1] = self.prev_h

        # All Predictions
        predictions = []

        # All Hot Encoded Inputs
        all_inputs = []

        # Generate Inputs
        input_locations = [self.gram_to_vocab[gram] for gram in self.data[self.cursor+1:self.cursor+self.T]]

        # Forward Propagation
        for i in xrange(len(input_locations)):
            # Get Location of Input and Output
            input_location = input_locations[i]
            output_location = input_locations[i] + 1

            # Generate Input
            inputs = np.zeros((self.vocab_size, 1))
            inputs[input_location, 0] = 1
            all_inputs.append(inputs)

            # Generate Output
            outputs = np.zeros((self.vocab_size, 1))
            outputs[output_location, 0] = 1

            # Move Input through Neural Network
            prediction, self.h[i] = self.forward_step(inputs, self.h[i - 1])
            predictions.append(prediction)

            # Calculate Loss
            loss += self.loss(prediction, output_location)

        # Backward Propagation
        dW2 = np.zeros_like(self.WY)
        dWh = np.zeros_like(self.WH)
        dW = np.zeros_like(self.WX)

        dbh = np.zeros_like(self.bh)
        dby = np.zeros_like(self.by)

        dhn = np.zeros_like(self.h[0])
        for i in reversed(xrange(len(input_locations))):
            d_outputs = np.copy(predictions[i])
            d_outputs[input_locations[i] + 1] -= 1

            # Compute Gradient for Output Layer
            dW2 += np.dot(d_outputs, self.h[i].T)

            # Compute Gradient for Output Bias
            dby += np.sum(d_outputs, axis=0, keepdims=True)

            # Compute Gradient for Hidden Layer
            dhidden = np.dot(self.WY.T, d_outputs) + dhn
            dhidden_deactivated = (1 - self.h[i] * self.h[i]) * dhidden
            dWh += np.dot(dhidden_deactivated, self.h[i - 1].T)

            # Compute Gradient for Hidden Bias
            dbh += np.sum(dhidden_deactivated, axis=0, keepdims=True)

            # Compute Gradient for Input Layer
            dW += np.dot(dhidden_deactivated, all_inputs[i].T)

            # Update Next Hidden State Gradient
            dhn = np.dot(self.WH.T, dhidden_deactivated)

        # Perform Parameter Update (Adam)
        for param, grad, m, v in zip([self.WX, self.WH, self.WY, self.bh, self.by],
                                      [dW, dWh, dW2, dbh, dby],
                                      [self.mdW, self.mdWh, self.mdW2, self.mbh, self.mby],
                                      [self.vdW, self.vdWh, self.vdW2, self.vbh, self.vby]):
            m = 0.9 * m + (1 - 0.9) * grad
            v = 0.99 * v + (1 - 0.99) * (grad**2)
            param += -self.learning_rate * m / (np.sqrt(v) + 1e-8)

        # Set Previous State
        self.prev_h = self.h[len(input_locations) - 1]

        # Increment Cursor
        self.cursor += self.T

        return loss

    def sample(self, n=100, temperature=1.0):
        # Sample
        sample = ""

        # Seed (Start Letter)
        seed = self.gram_to_vocab[self.data[self.cursor]]

        # Populate Sample with Seed
        sample += self.vocab[seed]

        # Generate sample input
        sample_input = np.zeros((self.vocab_size, 1))
        sample_input[seed, 0] = 1

        # Internal State for Sample
        sample_h = np.copy(self.prev_h)

        for i in xrange(n):
            # Move Inputs Through Neural Network
            sample_output, sample_h = self.forward_step(sample_input, sample_h, temperature)
            idx = np.random.choice(range(self.vocab_size), p=sample_output.ravel())

            sample += self.dl + self.vocab[idx]
            # Generate new Inputs
            sample_input = np.zeros((self.vocab_size, 1))
            sample_input[idx, 0] = 1

        return sample

    def train(self, data, ngrams=7, dl=" "):
        # Set Delimiter
        self.dl = dl

        # Split Data by ngrams
        if self.dl == "":
            words = list(data)
        else:
            words = data.split(dl)
        self.data = [dl.join(words[i:i+ngrams]) for i in range(len(words))[::ngrams]]

        # Get Unique Data
        self.unique_data = unique(self.data)

        # Generate map to access gram from index
        self.vocab = {i:gram for i,gram in enumerate(self.unique_data)}

        # Generate map to access index from gram
        self.gram_to_vocab = {gram:i for i,gram in enumerate(self.unique_data)}

        # Total Vocabulary Size
        self.vocab_size = len(self.vocab)

        # Timesteps to Move through Network
        data_len = len(self.data) - 1
        self.T = data_len if data_len < 25 else 25

        # Initialize Weights
        self.WX = np.random.randn(self.hiddenLayers, self.vocab_size)*0.01 # Input to Hidden
        self.WY = np.random.randn(self.vocab_size, self.hiddenLayers)*0.01 # Hidden to Output

        # Initialize Bias
        self.bh = np.zeros((self.hiddenLayers, 1)) # Hidden Layer
        self.by = np.zeros((self.vocab_size, 1)) # Output Layer

        # Initialize Gradient Cache
        self.mdW = np.zeros_like(self.WX)
        self.mdWh = np.zeros_like(self.WH)
        self.mdW2 = np.zeros_like(self.WY)
        self.mbh = np.zeros_like(self.bh)
        self.mby = np.zeros_like(self.by)

        self.vdW = np.zeros_like(self.WX)
        self.vdWh = np.zeros_like(self.WH)
        self.vdW2 = np.zeros_like(self.WY)
        self.vbh = np.zeros_like(self.bh)
        self.vby = np.zeros_like(self.by)

    def save(self):
        pickle.dump(self, open("rnn_dump", "w+"))

    def load(self, dump):
        return pickle.load(dump)

    def run(self, epochs, num_samples=100, temperature=1.0):
        for i in xrange(epochs):
            loss = 0
            count = 0
            while self.cursor+self.T < len(self.data):
                loss = self.step()
                if count % 10 == 0:
                    log = '======= Epoch: ' + str(i + 1) + '  Loss: ' + str(loss) + ' ======='
                    print '=' * len(log)
                    print self.sample(num_samples, temperature)
                    print log
                count += 1
            self.cursor = 0

epochs = 1
bot = RNN()
try:
    try:
        dump = open("rnn_dump")
        bot = bot.load(dump)
        bot.cursor = 0
    except:
        bot.train(open("data.txt").read())
    finally:
        bot.run(epochs)
except:
    print '======= Saving Data To "rnn_dump" ======='
    # bot.save()
    pass
