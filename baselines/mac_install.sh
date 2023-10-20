#!/bin/bash

print('Setting up \"poke\" conda environment ... ')
conda create -n poke python=3.11
print('Activating \"poke\" evironment ... ')
conda activate poke

print('Installing dependencies via pip ...')
pip install numpy einops matplotlib scikit-image pyboy hnswlib mediapy pandas gymnasium stable-baselines3 tensorflow tensorboard
