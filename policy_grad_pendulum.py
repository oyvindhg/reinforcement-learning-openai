
#import os
#os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import frozen_lake_data
import numpy as np

def discount_rewards(r, g):
    """ take 1D float array of rewards and compute discounted reward """
    discounted_r = [0 for i in range(len(r))]
    running_add = 0
    for t in reversed(range(0, len(r))):
        running_add = running_add * g + r[t]
        discounted_r[t] = running_add
    return discounted_r


def run_pg(env, g):

    import tensorflow as tf
    from tensorflow.contrib.layers import fully_connected

    # 1: Specify the neural network architecture
    n_inputs = 4 # one number can specify the state
    n_hidden = 8 # it's a simple task, we don't need more hidden neurons
    n_hidden2 = 100
    n_hidden3 = 100
    n_outputs = 2 # prob of turning left, up, right and down

    learning_rate = 0.01

    tf.reset_default_graph()  # Clear the Tensorflow graph.

    initializer = tf.contrib.layers.variance_scaling_initializer()
    import tensorflow.contrib.slim as slim

    # 2: Build the neural network
    # network_input = tf.placeholder(tf.float32, shape=[None, n_inputs])
    # hidden = fully_connected(network_input, n_hidden, activation_fn=tf.nn.elu, weights_initializer=initializer)
    # #hidden2 = fully_connected(hidden, n_hidden2, activation_fn=tf.nn.elu, weights_initializer=initializer)
    # #hidden3 = fully_connected(hidden2, n_hidden3, activation_fn=tf.nn.elu, weights_initializer=initializer)
    # logits = fully_connected(hidden, n_outputs, activation_fn=None, weights_initializer=initializer)
    # outputs = tf.nn.softmax(logits)

    network_input = tf.placeholder(shape=[None, n_inputs], dtype=tf.float32)
    hidden = slim.fully_connected(network_input, n_hidden, biases_initializer=None, activation_fn=tf.nn.relu)
    outputs = slim.fully_connected(hidden, n_outputs, activation_fn=tf.nn.softmax, biases_initializer=None)
    chosen_action = tf.argmax(outputs, 1)


    # 3: Select a random action based on the estimated probabilities
    p_actions = tf.concat(axis=1, values=[outputs])
    sel_action = tf.multinomial(tf.log(p_actions), num_samples=1)[0][0]


    # 4: Define functions for policy gradient
    reward_holder = tf.placeholder(shape=[None], dtype=tf.float32)
    action_holder = tf.placeholder(shape=[None], dtype=tf.int32)

    indexes = tf.range(0, tf.shape(outputs)[0]) * tf.shape(outputs)[1] + action_holder

    responsible_outputs = tf.gather(tf.reshape(outputs, [-1]), indexes)

    chosen_output = tf.gather(outputs[0][:], action_holder)

    tvars = tf.trainable_variables()

    loss = -tf.reduce_mean(tf.log(responsible_outputs) * reward_holder) #Create value for action that led to some reward
    gradients = tf.gradients(loss, tvars)

    gradient_holders = []
    for i, var in enumerate(tvars):
        placeholder = tf.placeholder(tf.float32, name=str(i) + '_holder')
        gradient_holders.append(placeholder)


    # 5: Function for getting best output
    best_action = tf.argmax(outputs, 1)


    # 6: Initialize network
    optimizer = tf.train.AdamOptimizer(learning_rate)
    update_batch = optimizer.apply_gradients(zip(gradient_holders, tvars))

    init = tf.global_variables_initializer()


    # 7: Training
    total_episodes = 5000  # Set total number of episodes to train agent on
    max_steps = 1000       # Set maximum number of steps per episode
    ep_per_update = 5   # Train the policy after this number of episodes


    with tf.Session() as sess:
        sess.run(init)
        ep_c = 0
        total_reward = []
        total_lenght = []

        gradBuffer = sess.run(tf.trainable_variables())
        for ix, grad in enumerate(gradBuffer):
            gradBuffer[ix] = grad * 0

        while ep_c < total_episodes:
            s = env.reset()
            running_reward = 0
            ep_history = []
            obs_history = []
            action_history = []
            reward_history = []

            for j in range(max_steps):
                # Probabilistically pick an action given our network outputs.
                a = sess.run(sel_action, feed_dict={network_input: np.reshape(s, (1, n_inputs))})

                obs_history.append(s)

                twist_strength = [(a - 50) / 25]

                s1, r, d, _ = env.step(twist_strength)  # Get our reward for taking an action given a bandit.
                ep_history.append([s, a, r, s1])
                action_history.append(a)

                s = np.array(s)

                reward_history.append(r)

                s = s1
                running_reward += r
                if d == True:
                    # Update the network.

                    break

            reward_history = discount_rewards(reward_history, g)
            ep_history = np.array(ep_history)
            ep_history[:, 2] = discount_rewards(ep_history[:, 2], g)
            feed_dict = {reward_holder: reward_history,
                         action_holder: action_history, network_input: np.vstack(obs_history)}
            grads = sess.run(gradients, feed_dict=feed_dict)
            for i, grad in enumerate(grads):
                gradBuffer[i] += grad

            if ep_c % ep_per_update == 0 and i != 0:

                feed_dict = dict(zip(gradient_holders, gradBuffer))
                sess.run(update_batch, feed_dict=feed_dict)


                for i, grad in enumerate(gradBuffer):
                    gradBuffer[i] = grad * 0

            total_reward.append(running_reward)


                    # Update our running tally of scores.
            if ep_c % 100 == 0:
                print(np.mean(total_reward[-100:]))
            ep_c += 1