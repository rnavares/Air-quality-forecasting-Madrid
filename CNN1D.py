#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 10 17:32:56 2017

@author: dvalput
"""

import numpy as np

# Keras imports
from keras.models import Sequential
from keras.layers import Dense
from keras import regularizers
from keras import optimizers
from keras.callbacks import EarlyStopping
from keras.layers import Flatten
from keras.layers.convolutional import Conv1D
from keras.layers.convolutional import MaxPooling1D

from evaluate_forecast import evaluate_forecast
from normalization import normalize_by_columns_maxmin, denormalize_maxmin


# Set the forecasting horizon:
k_hrs = 6

# Time delays to be used
########################################################################
#t, t-1, t-2, t-12, t-13, t-14, t-36, t-37, t-60
which_no2 = np.array([0, 1, 2, k_hrs, k_hrs+1, k_hrs+2, k_hrs+24, k_hrs+25, k_hrs+26, k_hrs+48, k_hrs+49, k_hrs+50])

# Which meteo data should I take? 0 - the time t, 1 - the time t-1...
which_meteo = np.array([0, 1, 2, k_hrs, k_hrs+1, k_hrs+2])

# which traffic samples from the past
which_traffic = np.array([0, 1, 2, k_hrs, k_hrs+1, k_hrs+2])

# for other pollutants: co, no, so2
which_other_pollutants = np.array([0, 1, 2, k_hrs, k_hrs+1, k_hrs+2, k_hrs+24, k_hrs+25, k_hrs+26])

#######################################################################
# Redefining time delays for k_hrs other than 6, 12, 24.
if k_hrs < 6:
    which_no2 = np.array([0, 1, 2, k_hrs+24, k_hrs+25, k_hrs+26, k_hrs+48, k_hrs+49, k_hrs+50])

    which_meteo = np.array([0, 1, 2])

    which_traffic = np.array([0, 1, 2])

    which_other_pollutants = np.array([0, 1, 2, k_hrs+24, k_hrs+25, k_hrs+26])

if k_hrs == 48:
    which_no2 = np.array([0, 1, 2, k_hrs - 24, k_hrs - 23, k_hrs - 22, k_hrs, k_hrs+1, k_hrs+2, k_hrs+24, k_hrs+25, k_hrs+26, k_hrs+48, k_hrs+49, k_hrs+50])

    which_meteo = np.array([0, 1, 2, k_hrs - 24, k_hrs - 23, k_hrs - 22, k_hrs, k_hrs+1, k_hrs+2])

    which_traffic = np.array([0, 1, 2, k_hrs - 24, k_hrs - 23, k_hrs - 22, k_hrs, k_hrs+1, k_hrs+2])

    which_other_pollutants = np.array([0, 1, 2, k_hrs - 24, k_hrs - 23, k_hrs - 22, k_hrs, k_hrs+1, k_hrs+2, k_hrs+24, k_hrs+25, k_hrs+26])


# LOAD THE DATA
X = np.loadtxt("train_examples/train_examples_" + str(k_hrs) + "hrs")
y = np.loadtxt("targets/targets_" + str(k_hrs) + "hrs")

# Which features do you want to use? Set it to True. NO2 is used by default.
meteo = True
extra = True
hod = True  # included in extra for now
traffic_intensidad = True
traffic_carga = False
ensemble = True
co = True
so2 = True
no = True

# CAMS
neighbourhood_size = 9  # the number of points I am using around Pza de España
##############################################################################
# Length of the data
no2_len = len(which_no2)
meteo_len = len(which_meteo)
traffic_len = len(which_traffic)
pollutants_len = len(which_other_pollutants)
macc_len = neighbourhood_size
extra_len = 4 # four extra features, hc for now

# Create start indices for each feature in X

start_no2 = 0
start_meteo = no2_len
start_extra = no2_len + 4 * meteo_len
start_co = start_extra + 4
start_no = start_co + pollutants_len
start_so2= start_no + pollutants_len
start_intensidad = start_so2 + pollutants_len
start_carga = start_intensidad + traffic_len
start_macc = start_carga + traffic_len

# lists of indices to include
list_no2 = list(range(start_no2, no2_len))
list_meteo = list(range(start_meteo, start_extra))
list_extra = list(range(start_extra, start_co))
list_co = list(range(start_co, start_no))
list_no = list(range(start_no, start_so2))
list_so2 = list(range(start_so2, start_intensidad))
list_intensidad =list(range(start_intensidad, start_carga))
list_carga = list(range(start_carga, start_macc))
list_macc = list(range(start_macc, start_macc + macc_len))
# total list of all indices to take into model training from the matrix X
list_all_features = list_no2 # no2 is always used
if meteo: list_all_features += list_meteo
if extra: list_all_features += list_extra
if co: list_all_features += list_co
if no: list_all_features += list_no
if so2: list_all_features += list_so2
if traffic_carga: list_all_features += list_intensidad
if traffic_intensidad: list_all_features += list_carga
if ensemble: list_all_features += list_macc

# Remove unwanted features from X (columns).
X = X[:, list_all_features]

# Randomly shuffle the training examples
X = np.hstack([X, y.reshape(-1,1)])
# set the random seed and shuffle the matrix X
np.random.seed(2)
np.random.shuffle(X)
# split again targets and training examples
y = X[:,-1]
X = X[:,0:-1]


# number of training examples
m = X.shape[0]

n_folds = 10
runs = 5

fold_size = int(m/n_folds)

# Errors for hybrid model: ANN + RF
error_mat = np.zeros((runs + 1, 10), dtype=float)  # the last row is for averages over all the runs
error_mat_folds = np.zeros((n_folds + 1, 10), dtype=float)
##############################################################
# 10-folds cross-validation
fold_size = int(m/n_folds)
folds_idx = [x for x in range(0, m, fold_size)]
folds_idx[-1] = m

##############################################################
# Neural network parameters
"""
Here set the parameters of the FNN (depth, number of hidden neurons, etc.)
"""
input_layer_size = X.shape[1]


num_outputs = 1

# normalizing the training examples and targets
X, y, maxNO2, minNO2 = normalize_by_columns_maxmin(X, y)
for k in range(n_folds):
    # take the k-th fold for validation
    X_test = X[folds_idx[k]:folds_idx[k+1] , :]
    y_test = y[folds_idx[k]:folds_idx[k+1]]
    # ... and the rest goes into training
    X_train = np.delete(X, list(range(folds_idx[k], folds_idx[k+1])), axis = 0)
    y_train = np.delete(y, list(range(folds_idx[k], folds_idx[k+1])))

    for run in range(0, runs):
        ############### DEFINE A CNN  ##################
        X_train_reshaped = X_train.reshape((X_train.shape[0], X_train.shape[1], 1))

        model = Sequential()

        model.add(Conv1D(filters=32, kernel_size=5, activation='relu', input_shape=(X_train.shape[1], 1)))
        model.add(MaxPooling1D(pool_size=2))
        model.add(Flatten())
        # model.add(Dense(100, activation='relu'))
        model.add(Dense(10, activation='relu'))
        model.add(Dense(1))



        #Examine the network
        # print (model.summary())

        ###################### TRAIN THE NET  ################################
        # Compile the model
        model.compile(optimizer='adam', loss='mse')
        # fit model
        model.fit(X_train_reshaped, y_train, epochs=300, verbose=0)


        # Evaluate the model
        scores = model.evaluate(X_train_reshaped, y_train) # evaluating on training data

        # Calculate predictions on the train set X
        predictions = model.predict(X_train_reshaped) # evaluating on training data

         ################# TEST AND TRAIN ERROR ###############################
        # Training error
        # the predictions for the training set are in the variable "predictions"
        pred_train = denormalize_maxmin(predictions, maxNO2, minNO2)
        pred_train = np.reshape(pred_train, (len(pred_train), ))
        y_train_denorm = denormalize_maxmin(y_train, maxNO2, minNO2)

        rmse_train, mae_train, ia_train, mb_train, pears_train = evaluate_forecast(y_train_denorm, pred_train, normalize=0)

        # Validation error
        X_test_reshaped = X_test.reshape((X_test.shape[0], X_test.shape[1], 1))
        pred_test = model.predict(X_test_reshaped)   # calculate the predictions on the test set
        pred_test = np.reshape(pred_test, (len(pred_test), ))
        pred_test = denormalize_maxmin(pred_test, maxNO2, minNO2)
        y_test_denorm = denormalize_maxmin(y_test, maxNO2, minNO2)

        rmse_test, mae_test, ia_test, mb_test, pears_test = evaluate_forecast(y_test_denorm, pred_test, normalize=0)

        ##########################################################################
        ####################### Save the results into a matrix  ##################
        error_mat[run,:] = np.array([rmse_train, rmse_test, mae_train,  mae_test, ia_train, ia_test, mb_train, mb_test, pears_train, pears_test])

    # Calculate the means, outside the for loop
    error_mat[runs, :] = sum(error_mat[:-1,:]) / len(error_mat[:-1,:])
    error_mat_folds[k, :] = error_mat[runs, :]
    print("Fold", str(k+1), "finished.\n")

# Calculate the average over all folds
error_mat_folds[n_folds, :] = np.mean(error_mat_folds[0:n_folds,:], axis = 0)
error_mat_folds.shape
import pandas as pd
results = pd.DataFrame(error_mat_folds)
results.columns = ['rmse_train', 'rmse_test', 'mae_train',  'mae_test',
                   'ia_train', 'ia_test', 'mb_train', 'mb_test',
                   'pears_train', 'pears_test']

results['rmse_test'].values.mean()
results.to_csv('CNN1D_4_t6.csv')
