#%%[markdown]
# # Resume training the model after interruption WITHOUT validation (use the entire training set).

#%%[markdown]
# ## Imports

#%%
import os
import pathlib
import pickle
from datetime import datetime
from multiprocessing import cpu_count

import joblib
import pandas as pd
import tensorflow as tf
from gensim.sklearn_api import W2VTransformer
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

from components_mimic import (TransformedGenerator, check_ipynb, data,
                        neural_network, pse_helper_functions, visualization)

#%%[markdown]
# ## Global variables

#%%[markdown]
# ### Save path
#
# SAVE_DIR specifies where the data from the partially trained
# model will be loaded. Must be a subdirectory of "model".
# Will continue saving there.

#%%
SAVE_DIR = '20190813-2105training'
save_path = os.path.join('mimic', 'model', SAVE_DIR)

#%%[markdown]
# ## Execution

#%%[markdown]
# ### Jupyter notebook detection
#
# Check if running inside Jupyter notebook or not (will be used later for Keras progress bars)

#%%
in_ipynb = check_ipynb().is_inipynb()

#%%[markdown]
# ### Data
#
# Load the data to resume the training

#%%[markdown]
# #### Load the data

#%%
N_TRAINING_EPOCHS, BATCH_SIZE, SEQUENCE_LENGTH, W2V_EMBEDDING_DIM = joblib.load(os.path.join(save_path, 'hp.joblib'))

d = data()

if os.path.isfile(os.path.join(save_path, 'sampled_encs.pkl')):
	enc_file = os.path.join(save_path, 'sampled_encs.pkl')
	print('Loaded partially completed experiment was done with RESTRICTED DATA !')
else:
	enc_file = False

d.load_data(previous_encs_path=enc_file, get_profiles=False)

#%%[markdown]
# #### Make the data lists

#%%
_, targets_train, seq_train, active_meds_train, depa_train, _, _, _, _ = d.make_lists(get_valid=False)

#%%[markdown]
# ### Word2vec embeddings
#
# Load the previously fitted word2vec pipeline

#%%
w2v = joblib.load(os.path.join(save_path, 'w2v.joblib'))

#%%[markdown]
# ### Profile state encoder (PSE)
#
# Load the previously fitted profile state encoder

#%%
phf = pse_helper_functions()
pse_pp = phf.pse_pp
pse_a = phf.pse_a

pse = joblib.load(os.path.join(save_path, 'pse.joblib'))

#%%[markdown]
# ### Label encoder
#
# Load the previously fitted label encoder

#%%
le = joblib.load(os.path.join(save_path, 'le.joblib'))

#%%[markdown]
# ### Neural network
#
# Load the partially fitted neural network and resume training

#%%[markdown]
# Load the number of epochs previously completed

#%%
with open(os.path.join(save_path, 'done_epochs.pkl'), mode='rb') as file:
	N_DONE_EPOCHS = pickle.load(file)

#%%[markdown]
# Get the variables necessary to train the model from
# the fitted scikit-learn pipelines.

#%%
w2v_step = w2v.named_steps['w2v']
pse_shape = sum([len(transformer[1].vocabulary_) for transformer in pse.named_steps['columntrans'].transformers_])
output_n_classes = len(le.classes_)

#%%[markdown]
# #### Sequence generators

#%%
train_generator = TransformedGenerator(w2v_step, pse, le, targets_train, seq_train, active_meds_train, depa_train, W2V_EMBEDDING_DIM, SEQUENCE_LENGTH, BATCH_SIZE)

#%%[markdown]
# #### Instantiate the model

#%%
n = neural_network()
callbacks = n.callbacks(save_path, callback_mode='train_no_valid', n_done_epochs=N_DONE_EPOCHS)
model = tf.keras.models.load_model(os.path.join(save_path, 'partially_trained_model.h5'), custom_objects={'sparse_top10_accuracy':n.sparse_top10_accuracy, 'sparse_top30_accuracy':n.sparse_top30_accuracy})

#%%[markdown]
# #### Resume training the model
#
# Use in_ipynb to check if running in Jupyter or not to print
# progress bars if in terminal and log only at epoch level if
# in Jupyter. This is a bug of Jupyter or Keras where progress
# bars will flood stdout slowing down and eventually crashing 
# the notebook.

#%%
if in_ipynb:
	verbose=2
else:
	verbose=1

model.fit_generator(train_generator,
	epochs=(N_TRAINING_EPOCHS-N_DONE_EPOCHS),
	callbacks=callbacks,
	verbose=verbose)

model.save(os.path.join(save_path, 'model.h5'))
