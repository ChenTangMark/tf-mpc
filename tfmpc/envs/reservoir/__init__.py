import gym
import numpy as np
import tensorflow as tf

from tfmpc.envs.diffenv import DiffEnv
from tfmpc.envs.gymenv import GymEnv


class Reservoir(DiffEnv, GymEnv):

    def __init__(self,
                 max_res_cap,
                 lower_bound,
                 upper_bound,
                 low_penalty,
                 high_penalty,
                 set_point_penalty,
                 downstream,
                 rain_shape,
                 rain_scale):
        super().__init__()

        self.max_res_cap = max_res_cap
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.low_penalty = low_penalty
        self.high_penalty = high_penalty
        self.set_point_penalty = set_point_penalty
        self.downstream = downstream
        self.rain_shape = rain_shape
        self.rain_scale = rain_scale

        self.obs_space = gym.spaces.Box(
            low=np.zeros_like(self.max_res_cap), high=np.array(self.max_res_cap))

        self.action_space = gym.spaces.Box(
            shape=[self.action_size, 1], low=0.0, high=1.0)

    @property
    def state_size(self):
        return len(self.lower_bound)

    @property
    def action_size(self):
        return self.state_size

    @tf.function
    def transition(self, state, action, batch=tf.constant(False)):
        rlevel = state
        outflow = self._outflow(action, state)

        vaporated = self._vaporated(state)

        rlevel_ = (
            rlevel
            + self.rain + self._inflow(outflow)
            - vaporated - outflow
        )
        return rlevel_

    @tf.function
    def cost(self, state, action, batch=tf.constant(False)):
        rlevel = state

        low = self.lower_bound
        high = self.upper_bound

        c1 = self.LOW_PENALTY * tf.maximum(0.0, low - rlevel)
        c2 = self.HIGH_PENALTY * tf.maximum(0.0, rlevel - high)
        c3 = self.SET_POINT_PENALTY * tf.abs((low + high) / 2.0 - rlevel)

        if batch:
            total_cost = tf.reduce_sum(
                tf.squeeze(c1 + c2 + c3, axis=-1),
                axis=-1)
        else:
            total_cost = tf.reduce_sum(c1 + c2 + c3)

        return total_cost

    @tf.function
    def final_cost(self, state):
        return self.cost(state, None)

    @tf.function
    def _vaporated(self, rlevel):
        return (1.0 / 2.0) * tf.sin(rlevel / self.BIGGESTMAXCAP) * rlevel

    @tf.function
    def _inflow(self, outflow):
        return tf.matmul(self.downstream, outflow, transpose_a=True)

    @tf.function
    def _outflow(self, relative_flow, rlevel):
        return relative_flow * rlevel

    def __repr__(self):
        return f"Reservoir({self.state_size})"

    def __str__(self):
        bounds = ", ".join(
            f"[{float(l):.2f}, {float(u):.2f}]"
            for l, u in zip(self.lower_bound, self.upper_bound))

        topology = self.downstream

        rain = ", ".join(f"{float(r):.2f}" for r in self.rain)
        rain = f"[{rain}]"

        return f"Reservoir(\nbounds={bounds},\ntopology=\n{topology},\nrain={rain})"

    @classmethod
    def load(cls, config):
        kwargs = {
            key: tf.constant(val, dtype=tf.float32)
            for key, val in config.items()
        }
        return cls(**kwargs)
