import tensorflow as tf
from tensorflow.keras import layers, models, optimizers

def build_dqn(state_dim, action_dim):
    model = models.Sequential([
        layers.Input(shape=(state_dim,)),
        layers.Dense(128, activation='relu'),
        layers.Dense(128, activation='relu'),
        layers.Dense(action_dim)
    ])
    model.compile(optimizer=optimizers.Adam(1e-3), loss='mse')
    return model
