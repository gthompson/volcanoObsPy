# -*-coding:Utf-8 -*

# Copyright: Marielle MALFANTE - GIPSA-Lab -
# Univ. Grenoble Alpes, CNRS, Grenoble INP, GIPSA-lab, 38000 Grenoble, France
# (04/2018)
#
# marielle.malfante@gipsa-lab.fr (@gmail.com)
#
# This software is a computer program whose purpose is to automatically
# processing time series (automatic classification, detection). The architecture
# is based on machine learning tools.
#
# This software is governed by the CeCILL license under French law and
# abiding by the rules of distribution of free software.  You can  use,
# modify and/ or redistribute the software under the terms of the CeCILL
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info".
#
# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability.
#
# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or
# data to be ensured and,  more generally, to use and operate it in the
# same conditions as regards security.
#
# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL

import json
import numpy as np
from os.path import isfile, isdir
from os import mkdir
import matplotlib
matplotlib.use('TkAgg')

#from sympy.ntheory import factorint
import matplotlib.pylab as plt
from scipy.signal import butter, lfilter, filtfilt
import scipy.signal as sg
import matplotlib.patches as patches
import pandas as pd
import glob
from datetime import datetime, timedelta
from featuresFunctions import energy, energy_u
from math import sqrt

from functools import reduce
def factorint(n):
    return set(reduce(list.__add__, ([i, n//i] for i in range(1, int(n++0.5) + 1) if n % i == 0)))

def display_cat(cat):
    """
    Display information about data contained in catalogue
    """
    print('Class\t<- length (s) ->\tskew')
    print('     \tmean\tstdev')
    for class_name in cat['class'].unique():
        L = cat[cat['class']==class_name]['length']
        print('%s\t%.2f\t%.2f\t\t%.2f' % (class_name, L.mean(), L.std(), L.skew() ) )
        
    return None

def bestFFTlength(n):
    """
    Computation can be super long for signal of length with a bad factorint.
    Compute fft on bestFFTlength points in this case.
    """
    while max(factorint(n)) >= 100:
        n -= 1
    return n

def butter_bandpass(lowcut, highcut, fs, order=5):
    """
    Butter bandpass filter design
    """
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def butter_bandpass_filter(data, lowcut, highcut, fs, order=5):
    """
    Butter filtering
    """
    if not lowcut or not highcut:
        return data
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = filtfilt(b, a, data)
    return y

def filter_data(data, fs, lowcut):
    data_filtered = []
    b = 0.08  # Transition band, as a fraction of the sampling rate (in (0, 0.5)).
    N = int(np.ceil((4 / b)))
    if not N % 2: N += 1  # Make sure that N is odd.
    n = np.arange(N)
    for i in range(0, np.shape(data)[0]):
        fc = lowcut/fs  # Cutoff frequency as a fraction of the sampling rate (in (0, 0.5)).
        # Compute a low-pass filter.
        h = np.sinc(2 * fc * (n - (N - 1) / 2.))
        w = np.blackman(N)
        h = h * w
        h = h / np.sum(h)
        # Create a high-pass filter from the low-pass filter through spectral inversion.
        h = -h
        h[int((N - 1) / 2)] += 1
        data_filtered.append(np.convolve(data[i], h))
    return np.array(data_filtered)


def print_cm(cm, labels, hide_zeroes=False, hide_diagonal=False, hide_threshold=None, max_str_label_size=10, float_display=False):
    """
    Pretty print for confusion matrixes
    Code adapted from GitHub zachguo
    """
    if max_str_label_size is None:
        columnwidth = max([len(x) for x in labels] + [5])  # 5 is value length
        bigcolumnwidth = columnwidth
    else:
        bigcolumnwidth = max([len(x) for x in labels] + [5])  # 5 is value length
        columnwidth = max_str_label_size + 3
    empty_cell = " " * columnwidth
    big_empty_cell = " " * bigcolumnwidth
    # Print header
    print(big_empty_cell*2 + 'Predicted class')
    print("    " + big_empty_cell, end=" ")
    for label in labels:
        # print("%{0}s".format(columnwidth) % label, end=" ")
        print("%{0}s".format(columnwidth) % label[:max_str_label_size], end=" ")

    print()
    # Print rows
    for i, label1 in enumerate(labels):
        print("    %{0}s".format(bigcolumnwidth) % label1, end=" ")
        for j in range(len(labels)):

            if not float_display:
                cell = "%{0}.0f".format(columnwidth) % cm[i, j] # For float formatting
            else:
                cell = "%{0}.1f".format(columnwidth) % cm[i, j] # For float formatting
            if hide_zeroes:
                cell = cell if float(cm[i, j]) != 0 else empty_cell
            if hide_diagonal:
                cell = cell if i != j else empty_cell
            if hide_threshold:
                cell = cell if cm[i, j] > hide_threshold else empty_cell
            print(cell, end=" ")
        print()

def display_observation(signal_large, f_min, f_max, fs, window_size_t, config, figure_title, figure_path):
    """
    Function used to display an observation, either to make observations to
    annotate, either to check predictions
    """
    # Get spectrofram window
    spectro_window_size = config.display['spectro_window_size']
    if config.display['window_type'] == 'kaiser':
        w = sg.kaiser(spectro_window_size, 18)
        w = w * spectro_window_size / sum([pow(j, 2) for j in w])
    else:
        print('window %s not implemented yet'%config.display['window_type'])
        return None
    # Get signal that will be displayed from input signal
    if config.display['decimate_factor'] is None :
        spectro_signal = signal_large
        fs_spectro = fs
    else:
        spectro_signal = sg.decimate(signal_large,config.display['decimate_factor'],zero_phase=True)
        fs_spectro = int(fs / config.display['decimate_factor'])
    # Compute spectrogram
    f, time, spec = sg.spectrogram(spectro_signal,
                       fs=fs_spectro,
                       nperseg=eval(config.display['nperseg']),
                       noverlap=eval(config.display['noverlap']),
                       nfft=eval(config.display['nfft']),
                       window=w,
                       scaling=config.display['scaling'])      # PSD in unit(x)**2/Hz
    if eval(config.display['dB']):
        spec_db = 10 * np.log10(spec)
    # Make figure and all the proper display on it
    fig = plt.figure(figsize=(15, 6))
    ax = fig.add_subplot(111)
    plt.pcolormesh(time, f, spec_db, shading='flat')#, vmin=30, vmax=85)
    cbar = plt.colorbar()
    cbar.set_label('Energy (dB)', size=25)
    cbar.ax.tick_params(labelsize=25)
    plt.xlabel('Time (s)', size=25)
    plt.ylabel('Frequency (Hz)', size=25)
    ax.tick_params(labelsize=25)
    # Plot the rectangle (observation)
    height=f_max-f_min
    plt.title(figure_title, size=25)
    my_rectangle = patches.Rectangle((window_size_t, f_min),
                                    window_size_t, height,alpha=1, facecolor='none',
                                    edgecolor='red',
                                    linewidth=5)
    ax.add_patch(my_rectangle)
    # Save everything
    plt.savefig(figure_path+'.png',format='png')
    plt.close('all')
    # And off you go !
    return

def getClasses(probas, threshold=None, thresholding=False):
    """
    Use self to return prediction result of a given signature (features as input)
    - features: features of the signature to analyze
    - return an array of probability
    """

    (n_data, n_classes) = np.shape(probas)
    maxes = np.max(probas, axis=1) # max(proba_on_classes) for each data

    # Find supposes classes where( proba == max(proba) ) for each data
    potentialClasses = [np.where(probas[i,:]==maxes[i])[0][0] for i in range(np.shape(maxes)[0])]

    # If thresholding
    if thresholding:
        assert len(threshold) == n_classes
        maxesUpdated = [-maxes[i] if maxes[i] < threshold[potentialClasses[i]] else maxes[i] for i in range(n_data)]
        potentialClassesUpdated = [-1 if maxes[i] < threshold[potentialClasses[i]] else potentialClasses[i] for i in range(n_data)]
        return potentialClassesUpdated, maxesUpdated

    # else
    else:
        return potentialClasses, maxes

def extract_features(config, signals, features, fs):
    """
    Function used to extract features outside of a recording environment
    """
    # (nData,_) = np.shape(signals)
    nData = np.shape(signals)[0]
    allFeatures = np.zeros((nData,),dtype=object)
    for i in range(np.shape(signals)[0]):
        signature = signals[i]
        # ... preprocessing
        if config.preprocessing['energy_norm']:
            E = energy(signature, arg_dict={'E_u':energy_u(signature)})
            signature = signature / sqrt(E)
        # ... features extraction
        features.compute(signature,fs)
        allFeatures[i] = features.featuresValues
    # Get proper shape (nData,nFeatures) instead of (nData,)
    allFeatures = np.vstack(allFeatures)
    return allFeatures
