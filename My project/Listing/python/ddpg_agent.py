import tensorflow as tf
import tensorflow.keras as keras
from tensorflow.keras.optimizers import Adam
from buffer import ReplayBuffer
from networks import Actor, Critic


alpha = 0.001
beta = 0.002
gamma = 0.99
tau = 0.005
noise = 0.1
batch_size = 64


class Agent:
    def __init__(self, input_dims, env=None, n_actions=2, 
                 max_size=1000000, fc1=400, fc2=300):
        self.gamma = gamma
        self.tau = tau
        self.memory = ReplayBuffer(max_size, input_dims, n_actions)
        self.batch_size = batch_size
        self.n_actions = n_actions
        self.noise = noise
        self.max_action = 1
        self.min_action = -1

        self.actor = Actor(n_actions=n_actions, name='actor')
        self.critic = Critic(name='critic')
        self.target_actor = Actor(n_actions=n_actions,
                                         name='target_actor')
        self.target_critic = Critic(name='target_critic')

        self.actor.compile(optimizer=Adam(learning_rate=alpha))
        self.critic.compile(optimizer=Adam(learning_rate=beta))
        self.target_actor.compile(optimizer=Adam(learning_rate=alpha))
        self.target_critic.compile(optimizer=Adam(learning_rate=beta))

        self.update_network_parameters(tau=1)
        
    def update_network_parameters(self, tau=None):
        if tau is None: 
            tau = self.tau
            
        weights = []
        targets = self.target_actor.weights
        for i, weight in enumerate(self.actor.weights):
            weights.append(weight * tau + targets[i]*(1-tau))
        self.target_actor.set_weights(weights)
        
        weights = []
        targets = self.target_critic.weights
        for i, weight in enumerate(self.critic.weights):
            weights.append(weight * tau + targets[i]*(1-tau))
        self.target_critic.set_weights(weights)
        
    def act(self, observation, evaluate = False):
        state = tf.convert_to_tensor([observation], dtype=tf.float32)
        actions = self.actor(state)
        if not evaluate:
            actions += tf.random.normal(shape=[self.n_actions],
                                        mean=0.0, stddev=self.noise)
            
        actions = tf.clip_by_value(actions, self.min_action, self.max_action)

        return actions
    
    def remember(self, state, action, reward, next_state, done):
        self.memory.store_transition(state, action, reward, next_state, done)
    
    def learn(self):
        if self.memory.mem_cntr < batch_size:
            return
        state, action, reward, next_state, done = \
            self.memory.sample_buffer(self.batch_size)
        
        states = tf.convert_to_tensor(state, dtype=tf.float32)
        states_ = tf.convert_to_tensor(next_state, dtype=tf.float32)
        rewards = tf.convert_to_tensor(reward, dtype=tf.float32)
        actions = tf.convert_to_tensor(action, dtype=tf.float32)
        
        with tf.GradientTape() as tape:
            target_actions = self.target_actor(states_)
            critic_value_ = tf.squeeze(self.target_critic(
                                states_, target_actions), 1)
            critic_value = tf.squeeze(self.critic(states, actions), 1)
            target = rewards + self.gamma*critic_value_*(1-done)
            critic_loss = keras.losses.MSE(target, critic_value)
        
        critic_net_gradient = tape.gradient(critic_loss, self.critic.trainable_variables)
        self.critic.optimizer.apply_gradients(zip(
            critic_net_gradient, self.critic.trainable_variables))
        
        with tf.GradientTape() as tape:
            new_policy_actions = self.actor(states)
            actor_loss = -self.critic(states, new_policy_actions)
            actor_loss = tf.math.reduce_mean(actor_loss)

        actor_network_gradient = tape.gradient(actor_loss,
                                               self.actor.trainable_variables)
        self.actor.optimizer.apply_gradients(zip(
            actor_network_gradient, self.actor.trainable_variables))

        self.update_network_parameters()


    def load_models(self):
        print("... loading models ...")
        self.actor.load_weights(self.actor.checkpoint_file)
        self.target_actor.load_weights(self.target_actor.checkpoint_file)
        self.critic.load_weights(self.critic.checkpoint_file)
        self.target_critic.load_weights(self.target_critic.checkpoint_file)


    def save_models(self):
        print('... saving models ...')
        self.actor.save_weights(self.actor.checkpoint_file)
        self.target_actor.save_weights(self.target_actor.checkpoint_file)
        self.critic.save_weights(self.critic.checkpoint_file)
        self.target_critic.save_weights(self.target_critic.checkpoint_file)