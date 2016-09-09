import csv 
import numpy as np
from keras.models import Sequential
from keras.layers import GRU, Dense, Activation, TimeDistributed
import nltk
import itertools

'''
Function: executable
Input: None
Output: None
Description: Trains a RNN with the zidisha natural language data
'''
def executable():
	storyMap = getStory()
	X_train, y_train = preprocessDataset(storyMap)
	model = TrainRNN(X_train, y_train, 100)

'''
Function: TrainRNN
Input: X_train = training features, Y_train = labels
Output: Trained Model
Description: A RNN using the Keras library trained on the training dataset.
'''
def TrainRNN(X_train, y_train, dim):
	model = Sequential()
	model.add(GRU(output_dim = 1, input_length = X_train.size / dim, input_dim = dim, return_sequences=True))
	model.add(Activation('relu'))
	model.add(TimeDistributed(Dense(1, activation='softmax')))
	model.compile(loss = 'binary_crossentropy', optimizer = 'adam', metrics = ['accuracy'])
	return model

'''
Function: preprocessDataset
Input: storyMap from getStory
Output: Training dataset ready to be passed into neural network
Description: This function preprocesses natural language data so that it is ready for training
'''
def preprocessDataset(storyMap):
	X_train = []
	y_train = []
	for key in storyMap:
		X_train.append(preprocessParagraph(storyMap[key][0]))
		y_train.append(np.asarray([storyMap[key][1]]))
	X_train = np.asarray(X_train).reshape((1,len(X_train),100))
	y_train = np.asarray(y_train).reshape((1, len(y_train), 1))	
	return X_train, y_train

'''
Function: preprocessParagraph
Input: A paragraph of text
Output: Training dataset ready to be passed into neural network
Description: This function preprocesses natural language data so that it is ready for training. 
			 It uses preprocessing techniques suggested from wildml.com
'''
def preprocessParagraph(paragraph):
	# Create a vocab dictionary to create a word --> index mapping
	sentences = nltk.sent_tokenize(paragraph)
	tokenized_sentences = [nltk.word_tokenize(sent) for sent in sentences]
	word_freq = nltk.FreqDist(itertools.chain(*tokenized_sentences))
	vocabulary_size = 5000
	vocab = word_freq.most_common(vocabulary_size-1)
	index_to_word = [x[0] for x in vocab]
	index_to_word.append("unknown_token")
	word_to_index = dict([(w,i) for i,w in enumerate(index_to_word)])
	for i, sent in enumerate(tokenized_sentences):
		tokenized_sentences[i] = [w if w in word_to_index else "unknown_token" for w in sent]
	# Create a training dataset with a max of 100 dimensions from the index lists
 	X_train = [[word_to_index[w] for w in sent] for sent in tokenized_sentences]
 	X_train = X_train[0:100] if len(X_train) > 100 else X_train
 	while len(X_train) < 100:
 		X_train.append(0)
	return np.asarray(X_train)

'''
Function: getStory
Input: None
Output: Dict with (url => [story, score]) mapping
Description: Gets the "Story" for each borrower from trainingset.csv file
'''
def getStory():
	storyMap = {}
	f = open('trainingset.csv')
	creader = csv.reader(f)
	for row in creader:
		storyMap[row[0]] = [row[14], row[16]]
	return storyMap

if __name__ == "__main__":
	executable()

