#%%[markdown]
# # Train and evaluate word2vec embeddings from sequences of drug orders

#%%[markdown]
# ## Imports

#%%
import os
import pathlib
import pickle
from datetime import datetime
from multiprocessing import cpu_count

import matplotlib.pyplot as plt
import pandas as pd
import scikitplot as skplt
import seaborn as sns
import umap
from gensim.sklearn_api import W2VTransformer
from mpl_toolkits import mplot3d
from sklearn import metrics
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
from sklearn.model_selection import GridSearchCV, cross_validate
from sklearn.pipeline import Pipeline

from components_mimic import check_ipynb

#%%[markdown]
# ## Global variables

#%%[markdown]
# ### Save path
#
# Where everything will get saved. Will create a subdirectory
# called model with another subdirectory inside it with
# the date and time this block ran.

#%%
SAVE_STAMP = datetime.now().strftime('%Y%m%d-%H%M')
SAVE_PATH = os.path.join(os.getcwd(), 'mimic', 'model', SAVE_STAMP + 'word2vec')
pathlib.Path(SAVE_PATH).mkdir(parents=True, exist_ok=True)

#%%[markdown]
# ### Word2vec hyperparameters
#
# #### Grid search hyperparameters
# This grid will be used when performing grid search

#%%
W2V_GRID = {
			'w2v__alpha': [0.01,0.013],
			'w2v__iter': [32,64],
			'w2v__size': [64,256],
			'w2v__hs': [0,1],
			'w2v__sg': [0,1],
			'w2v__min_count': [5],
			'w2v__workers':[1],
			}

#%%[markdown]
# ### Clustering hyperparameters
#
# #### Grid search hyperparameters
# This grid will be used when performing grid search

#%%
CLUST_GRID = {
			'ac__n_clusters': [5,6,7,8,9,10,11,12,13,14,15],
			}

#%%[markdown]
# ## Data
#
# Load the sequences

#%%
profiles_path = os.path.join(os.getcwd(), 'mimic', 'preprocessed_data_mimic', 'profiles_list.pkl')
print('Loading data from path: {}...'.format(profiles_path))
with open(profiles_path, mode='rb') as file:
	data = pickle.load(file)
data = list(data.values())
print('Data successfully loaded.')

#%%[markdown]
# ## Transformers
#
# Prepare the word2vec and clustering transformers

#%%[markdown]
# ### Word2vec transformer

#%%
w2v_pipe = Pipeline([
			('w2v', W2VTransformer()),
			])

#%%[markdown]
# ### Clustering transformer

#%%
clust_pipe = Pipeline([
			('ac', AgglomerativeClustering()),
			])

#%%[markdown]
# ## Helper functions 
#
# These are scoring functions that will be used to score
# the word2vec embeddings and the clustering of the embeddings.

#%%
in_ipynb = check_ipynb().is_inipynb()

def accuracy_scorer_gensim(pipe, X=None, y=None):
	acc_dict = pipe.named_steps['w2v'].gensim_model.wv.accuracy('mimic/data/eval_analogy.txt') # YOUR ANALOGY FILE HERE, see https://radimrehurek.com/gensim/models/keyedvectors.html#gensim.models.keyedvectors.WordEmbeddingsKeyedVectors.accuracy for specifications.
	accuracy = len(acc_dict[1]['correct'])/((len(acc_dict[1]['correct'])) + (len(acc_dict[1]['incorrect'])))
	print('Accuracy is : {:.3f}'.format(accuracy))
	return accuracy

def silhouette_scorer_cosine(pipe, X=None, y=None):
	clusters = pipe.named_steps['ac'].fit_predict(X)
	score = silhouette_score(X, clusters, metric='cosine')
	print('Score is: {}'.format(score))
	return score

#%%[markdown]
# ## Word2vec grid search
#
# Search for the best word2vec hyperparameters, then plot the results

#%%
print('Performing grid search for word2vec embeddings...')
w2v_gscv = GridSearchCV(w2v_pipe, W2V_GRID, scoring={'acc':accuracy_scorer_gensim}, cv=3, refit='acc', error_score=0, return_train_score=False, n_jobs=-2, verbose=1) # n_jobs=-2 otherwise is too cpu intensive and hangs the machine
w2v_gscv.fit(data)

# Convert results to a dataframe and save it
print('Saving results of grid search for word2vec embeddings...')
w2v_gscv_results_df = pd.DataFrame.from_dict(w2v_gscv.cv_results_)
w2v_gscv_results_df.to_csv(os.path.join(SAVE_PATH,'word2vec_gridsearch_results.csv'))
# Sort by rank
w2v_gscv_results_df.set_index('rank_test_acc', inplace=True)
# Select only useful columns
w2v_gscv_results_filtered = w2v_gscv_results_df[['split0_test_acc', 'split1_test_acc', 'split2_test_acc']].copy()
# Rename columns to clearer names
w2v_gscv_results_filtered.rename(inplace=True, index=str, columns={'split0_test_acc': 'Test analogy score', 'split1_test_acc': 'Test analogy score', 'split2_test_acc': 'Test analogy score'})
# Structure the dataframe as expected by Seaborn
w2v_gscv_results_graph_df = w2v_gscv_results_filtered.stack().reset_index()
w2v_gscv_results_graph_df.rename(inplace=True, index=str, columns={'rank_test_acc':'Rank', 'level_1':'Metric', 0:'Result'})
# Make sure the epochs are int to avoid weird ordering effects in the plot
w2v_gscv_results_graph_df['Rank'] = w2v_gscv_results_graph_df['Rank'].astype('int8')
# Plot
sns.set(style='darkgrid')
sns.relplot(x='Rank', y='Result', hue='Metric', kind='line', data=w2v_gscv_results_graph_df)
# Output the plot
if in_ipynb:
	plt.show()
else:
	plt.savefig(os.path.join(SAVE_PATH, 'word2vec_grid_search_results.png'))
# Clear
plt.gcf().clear()

#%%[markdown]
# ## Clustering grid search
#
# Search for the best clustering hyperparameters from the
# fitted w2v grid search, then plot the results

#%%
print('Reducing dimensionality of word2vec embeddings for clustering...')
# Get the normalized word2vec embeddings
w2v_gscv.best_estimator_.named_steps['w2v'].gensim_model.init_sims(replace=True)
vectors = w2v_gscv.best_estimator_.named_steps['w2v'].gensim_model.wv.vectors
# Reduce dimensionality to 3D using UMAP
umapper = umap.UMAP(n_components=3)
umap_vectors = umapper.fit_transform(vectors)

#%%
# Do the clustering
print('Performing grid search for clustering...')
clust_gscv = GridSearchCV(clust_pipe, CLUST_GRID, scoring={'sil':silhouette_scorer_cosine}, cv=3, refit='sil', error_score=0, return_train_score=False, n_jobs=-2, verbose=1) # n_jobs=-2 otherwise is too cpu intensive and hangs the machine
clust_gscv.fit(umap_vectors)

# Convert results to a dataframe and save it
print('Saving results of grid search for clustering...')
clust_cv_results_df = pd.DataFrame.from_dict(clust_gscv.cv_results_)
clust_cv_results_df.to_csv(os.path.join(SAVE_PATH, 'clustering_grid_search_results.csv'))
# You want this to be sorted by number of clusters otherwise weird plot
clust_cv_results_df.sort_values(by='param_ac__n_clusters', inplace=True)
# Select only useful columns
clust_cv_results_filtered = clust_cv_results_df[['param_ac__n_clusters', 'split0_test_sil', 'split1_test_sil', 'split2_test_sil']].copy()
# Rename columns to clearer names
clust_cv_results_filtered.rename(inplace=True, index=str, columns={'split0_test_sil': 'Test silhouette', 'split1_test_sil': 'Test silhouette', 'split2_test_sil': 'Test silhouette', 'param_ac__n_clusters':'k'})
# Structure the dataframe as expected by Seaborn
clust_cv_results_graph_df = clust_cv_results_filtered.set_index('k').stack().reset_index()
clust_cv_results_graph_df.rename(inplace=True, index=str, columns={'level_1':'Metric', 0:'Result'})
# Plot
sns.set(style='darkgrid')
sns.relplot(x='k', y='Result', hue='Metric', kind='line', data=clust_cv_results_graph_df)
# Output the plot
if in_ipynb:
	plt.show()
else:
	plt.savefig(os.path.join(SAVE_PATH, 'cluster_grid_search_results.png'))
# Clear
plt.gcf().clear()

#%%[markdown]
# ## Final embeddings

# Get final accuracy
acc = accuracy_scorer_gensim(w2v_gscv.best_estimator_)
# Get the embeddings
vectors = w2v_gscv.best_estimator_.named_steps['w2v'].gensim_model.wv.vectors
# Reduce dimensionality for clustering and plotting
print('Reducing dimensionality of final word2vec embeddings for clustering...')
umapper = umap.UMAP(n_components=3)
umap_vectors = umapper.fit_transform(vectors)
# Cluster
print('Performing clustering...')
clusters = clust_gscv.best_estimator_.fit_predict(umap_vectors)

# Plot the silhouette graph
print('Plotting silhouette graph...')
skplt.metrics.plot_silhouette(umap_vectors, clusters, metric='cosine')
# Output the plot
if in_ipynb:
	plt.show()
else:
	plt.savefig(os.path.join(SAVE_PATH, 'silhouette_plot.png'))
# Clear
plt.gcf().clear()

# Plot the 3d clustered embeddings
# Make a list of 3d coordinates and and associated cluster for each drug
print('Plotting clustered 3d-UMAP projected embeddings...')
graph_data = []
index2entity = w2v_gscv.best_estimator_.named_steps['w2v'].gensim_model.wv.index2entity
for umapcoords, cluster, entity in zip(umap_vectors, clusters, index2entity):
	graph_data.append([umapcoords[0], umapcoords[1], umapcoords[2], cluster, entity])
# Convert to dataframe
graph_data_df = pd.DataFrame(data=graph_data, columns=['x', 'y', 'z', 'cluster', 'entity'])
# Save the dataframe (to eventually manually label clusters)
graph_data_df.sort_values(by='cluster', inplace=True)
graph_data_df.to_csv(os.path.join(SAVE_PATH, 'graph_dataframe.csv'))
# Plot
ax = plt.figure(figsize=(16,10)).gca(projection='3d')
ax.scatter(
	xs=graph_data_df['x'] ,
	ys=graph_data_df['y'] ,
	zs=graph_data_df['z'] ,
	c=graph_data_df['cluster'],
	cmap='prism'
)
# Output the plot
if in_ipynb:
	plt.show()
else:
	plt.savefig(os.path.join(SAVE_PATH, 'clusted_embeddings_plot.png'))
# Clear
plt.gcf().clear()

#%%
print('Best hyperparameters for word2vec embeddings: {}'.format(w2v_gscv.best_params_))

#%%
