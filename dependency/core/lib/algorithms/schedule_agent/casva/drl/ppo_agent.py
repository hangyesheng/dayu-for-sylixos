import torch
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
import copy
import os

from .network import Actor, Critic

__all__ = ('DualClippedPPO',)


class DualClippedPPO(object):
    def __init__(
            self,
            state_dims,
            action_dim,
            gamma=0.99,
            hid_shape=(256, 256),
            conv_kernel_size=(3, 3),
            conv_hid_channels=(16, 64),
            conv_state_features=64,
            a_lr=1e-4,
            c_lr=1e-4,
            tau=0.005,
            batch_size=256,
            epsilon=0.2,
            value_clip=3,
            device='cpu',
            **param
    ):
        # Initialize Actor and Critic networks
        self.actor = Actor(state_dims, action_dim, hid_shape,
                           conv_hid_channels, conv_kernel_size,
                           conv_state_features).to(device)
        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=a_lr)

        self.critic = Critic(state_dims, action_dim, hid_shape,
                             conv_hid_channels, conv_kernel_size,
                             conv_state_features).to(device)
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr=c_lr)

        # Target Critic for value target
        self.critic_target = copy.deepcopy(self.critic)
        for p in self.critic_target.parameters():
            p.requires_grad = False

        # Hyperparameters
        self.gamma = gamma
        self.tau = tau
        self.batch_size = batch_size
        self.epsilon = epsilon
        self.value_clip = value_clip
        self.device = device
        self.action_dim = action_dim

    def select_action(self, state, deterministic=False, with_logprob=False):
        # Select action based on the current policy
        with torch.no_grad():
            state = torch.FloatTensor(state).to(self.device)
            action, log_prob = self.actor(state, deterministic, with_logprob)
        return action.cpu().numpy().flatten()

    def train(self, replay_buffer):
        # Sample a batch from replay buffer
        s, a, r, s_prime, done_mask = replay_buffer.sample(self.batch_size)

        # ---------------------------- Compute Target Value ----------------------------- #
        with torch.no_grad():
            # Get next state action using actor network
            a_prime, log_pi_a_prime = self.actor(s_prime)
            target_value = self.critic_target(s_prime, a_prime)
            target_value = r + (1 - done_mask) * self.gamma * target_value

        # ---------------------------- Update Critic (Value Function) ----------------------------- #
        current_value = self.critic(s, a)

        # Clipped value loss
        value_loss_clip = torch.max(
            (current_value - target_value).pow(2),
            (torch.clamp(current_value - target_value, -self.value_clip, self.value_clip)).pow(2)
        ).mean()

        self.critic_optimizer.zero_grad()
        value_loss_clip.backward()
        self.critic_optimizer.step()

        # ---------------------------- Update Actor (Policy Network) ----------------------------- #
        # Freeze Critic network to avoid updating it during policy update
        for p in self.critic.parameters():
            p.requires_grad = False

        # Compute the ratio of new and old policies (Probability ratio)
        a, log_pi_a = self.actor(s)
        ratio = torch.exp(log_pi_a - log_pi_a.detach())

        # Compute the advantage estimate (using the clipped value loss)
        current_value = self.critic(s, a)
        advantage = target_value - current_value.detach()

        # PPO objective with dual clipping
        policy_loss_clip = -torch.min(
            ratio * advantage,
            torch.clamp(ratio, 1 - self.epsilon, 1 + self.epsilon) * advantage
        ).mean()

        # Update the actor
        self.actor_optimizer.zero_grad()
        policy_loss_clip.backward()
        self.actor_optimizer.step()

        # ---------------------------- Restore Critic Network Gradients ----------------------------- #
        for p in self.critic.parameters():
            p.requires_grad = True

        # ---------------------------- Soft Update of Target Critic ----------------------------- #
        for param, target_param in zip(self.critic.parameters(), self.critic_target.parameters()):
            target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)

    def save(self, save_dir, episode):
        assert os.path.exists(save_dir) and os.path.isdir(save_dir), f'Model saving directory "{save_dir}" error!'
        torch.save(self.actor.state_dict(), os.path.join(save_dir, f"ppo_actor_{episode}.pth"))
        torch.save(self.critic.state_dict(), os.path.join(save_dir, f"ppo_critic_{episode}.pth"))

    def load(self, load_dir, episode):
        assert os.path.exists(load_dir) and os.path.isdir(load_dir), f'Model loading directory "{load_dir}" error!'
        self.actor.load_state_dict(torch.load(os.path.join(load_dir, f"ppo_actor_{episode}.pth")))
        self.critic.load_state_dict(torch.load(os.path.join(load_dir, f"ppo_critic_{episode}.pth")))
