from collections import Counter
from options import FLAGS
import numpy as np
from gensim.models import word2vec
import random
import csv



def load_sentence(path, maxlen=20, minlen=5, max_size=-1):
	sents = []
	with open(path) as f:
		for line in f:
			if len(sents) == max_size:
				break
			toks = line.split()
			if len(toks) <= maxlen and len(toks) >= minlen:
				sents.append(toks)
	return sents

#pretrain word embeddings
def pretrain_emb(data):
	
	#train word2vec with external data and yelp
	sentences = word2vec.Text8Corpus('data/text8')
	model = word2vec.Word2Vec(sentences,min_count=10,size=FLAGS.dim_e)
	model.build_vocab(data,update=True)
	model.train(data,total_examples=model.corpus_count,epochs=50)
	

	#train word2vec on yelp directly
	'''
	model = word2vec.Word2Vec(iter=50,size=FLAGS.dim_e)
	model.build_vocab(data)
	model.train(data,total_examples=model.corpus_count,epochs=50)
	'''
	

	model.wv.save_word2vec_format(FLAGS.embedding_path)



def make_up(_x,n):
	x =[]
	for i in range(n):
		x.append(_x[i % len(_x)])
	return x

def get_batch(seq, src_syl, word2id, maxlen, label ,noisy=False):#x:sequences 2batch_size   y: style 2batch_size
	pad = word2id['<pad>']
	go = word2id['<go>']
	eos = word2id['<eos>']
	unk = word2id['<unk>']

	x_eos = []
	x_shift = []
	x_length=[]


	## do the padding
	for i  in range(len(seq)):
		sent_id = [word2id[w] if w in word2id else unk for w in seq[i]]
		l = len(seq[i])
		padding = [pad] * (maxlen - l)
		new_sent = sent_id + [eos] + padding
		x_eos.append(new_sent)
		x_shift.append([go]+new_sent[:-1])
		x_length.append(l)



	src_style = np.array(src_syl)
	src_seq = np.array(x_eos)
	length = np.array(x_length)
	seq_shift = np.array(x_shift)


	return {
		"src_seq" : src_seq, #batch_size * maxlen 
		"shifted_src_seq":seq_shift,
		"src_style" : src_style,
		"length" : length,
		"label" : label

	}
def get_data_id(datas,word2id,maxlen):
	pad = word2id['<pad>']
	eos = word2id['<eos>']
	unk = word2id['<unk>']
	d=[]
	for data in datas:
		sent_id = [word2id[i] if i in word2id else unk for i in data]
		l = len(data)
		padding = [pad] * (maxlen - l)
		new_sent = sent_id + [eos] + padding
		d.append(new_sent)
	return d

class dataloader(object):
	def __init__(self,dataset,trunc_size,
		maxlen=FLAGS.maxlen,
		minlen=FLAGS.minlen,
		batch_size=FLAGS.batch_size):

		self.batch_size = batch_size
		self.maxlen = maxlen
		self.minlen = minlen

		datas1=[]
		datas2=[]
		datas=[]
		for i in range(len(dataset)):
			train_path=FLAGS.train_path+dataset[i]+'/train'
			d1=load_sentence(train_path + '.0', maxlen = maxlen, minlen = minlen, max_size=trunc_size[i])
			datas1.append(d1)
			datas.extend(d1)
			d2=load_sentence(train_path + '.1', maxlen = maxlen, minlen = minlen, max_size=trunc_size[i])
			datas2.append(d2)
			datas.extend(d2)
			print('#sents of training file 0: {}'.format(len(datas1[i])))
			print('#sents of training file 1: {}'.format(len(datas2[i])))

			
		self.word2id = {'<go>':0,'<pad>':1,'<eos>':2, '<unk>':3}
		self.id2word = ['<go>','<pad>','<eos>','<unk>']
		
		minconut = 0
		#pretrain_emb(datas)
		words = [word for sent in datas for word in sent]
	
		cnt = sorted(Counter(words).items(), key=lambda obj: obj[0])

		cout = 0
		for word in cnt:
			if word[1] >= minconut and word[0]!='<pad>' and word[0]!='<go>' and word[0]!='<eos>' and word[0]!='<unk>':
				self.word2id[word[0]] = len(self.word2id)
				self.id2word.append(word[0])
			else:
				cout += 1
		
		self.vocab_size = len(self.word2id)
		print("vocabulary size is {}".format(self.vocab_size))

		print("unknow num:{}".format(cout))

		self.data_yelp=get_data_id(datas1[0]+datas2[0],self.word2id,self.maxlen)
		random.shuffle(self.data_yelp)
		self.data_amazon=get_data_id(datas1[1]+datas2[1],self.word2id,self.maxlen)
		random.shuffle(self.data_amazon)

		self.batches = []
		for i in range(len(dataset)):

			if len(datas1[i]) <len(datas2[i]):
				datas1[i] = make_up(datas1[i],len(datas2[i]))
			else:
				datas2[i] = make_up(datas2[i],len(datas1[i]))
			
			
			# sort the batch in sentence length, which will make the training more smooth
			datas1[i] = sorted(datas1[i],key=lambda j:len(j))
			datas2[i] = sorted(datas2[i],key=lambda j:len(j))

	
			n = len(datas1[i])
			s = 0
			t = s + int(batch_size/2)
			while t < n:
				self.batches.append(get_batch(datas1[i][s:t] + datas2[i][s:t],
				    [0]*(t-s) + [1]*(t-s) ,self.word2id, self.maxlen, i))
				s = t
				t = s + int(batch_size/2)

		random.shuffle(self.batches)

		self.batch_num = len(self.batches)
		self.pointer = -1


	def next_batch(self):
		self.pointer = (self.pointer + 1) % self.batch_num
		return self.batches[self.pointer]

	def reset(self):
		self.pointer = -1
	
	def random_batch(self):
		point_ran = np.random.randint(low = 0, high = self.batch_num-1)
		return self.batches[point_ran]

	def load_data(self,file):
		datas = load_sentence(file, maxlen = self.maxlen, minlen = self.minlen)
		pad = self.word2id['<pad>']
		go = self.word2id['<go>']
		eos = self.word2id['<eos>']
		unk = self.word2id['<unk>']

		x_eos = []


		## do the padding
		for sent in datas:
			sent_id = [self.word2id[w] if w in self.word2id else unk for w in sent]
			l = len(sent)
			if(l<=self.maxlen):
				padding = [pad] * (self.maxlen - l)
				new_sent = sent_id + [eos] + padding
				x_eos.append(new_sent)
		
		return x_eos

if __name__ == '__main__':
	#trunc = [70000,-1]
	#dataset=['yelp','amazon']
	trunc = [60000,60000]
	dataset=['yelp','amazon1']
	data = dataloader(dataset,trunc)
	print(data.vocab_size)

	#pretrain_emb(yelp_data.datas+amazon_data.datas)









