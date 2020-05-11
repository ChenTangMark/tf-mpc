import pytest
import tensorflow as tf

from tfmpc.envs import navigation
from tfmpc.solvers import ilqr


@pytest.fixture(params=[[[5.5], [-9.0]]])
def goal(request):
    return request.param


@pytest.fixture(params=[0.0, 5.0], ids=["beta=0.0", "beta=5.0"])
def beta(request):
    return request.param


@pytest.fixture(params=[None, [-1.0, 1.0]], ids=["unconstrained", "box"])
def bounds(request):
    return request.param


@pytest.fixture
def initial_state():
    return tf.constant([[0.0], [0.0]])


@pytest.fixture
def horizon():
    return tf.constant(10)


@pytest.fixture(scope="function")
def solver(goal, beta, bounds):
    goal = tf.constant(goal)
    beta = tf.constant(beta)
    low = high = None
    if bounds:
        low, high = bounds

    env = navigation.Navigation(goal, beta, low, high)
    return ilqr.iLQR(env)


def test_start(solver, initial_state, horizon):
    x0 = initial_state
    T = horizon
    states, actions = solver.start(x0, T)

    assert isinstance(states, tf.Tensor)
    assert states.shape == [T + 1, *x0.shape]
    assert tf.reduce_all(states[0] == x0)

    assert isinstance(actions, tf.Tensor)
    assert actions.shape == [T, *x0.shape]

    for t in range(T):
        x, u = states[t], actions[t]
        assert tf.reduce_all(states[t + 1] == solver.env.transition(x, u))


def test_backward(solver, initial_state, horizon):
    states, actions = solver.start(initial_state, horizon)
    K, k, J, delta_J = solver.backward(states, actions)

    action_size = solver.env.action_size
    state_size = solver.env.state_size

    assert isinstance(K, tf.Tensor)
    assert K.shape == [horizon, action_size, state_size]

    assert isinstance(k, tf.Tensor)
    assert k.shape == [horizon, action_size, 1]


def test_forward(solver, initial_state, horizon):
    x, u = solver.start(initial_state, horizon)
    K, k, J, delta_J = solver.backward(x, u)
    states, actions, costs, J_hat, residual = solver.forward(x, u, K, k)

    assert states.shape == x.shape
    assert actions.shape == u.shape
    assert costs.shape == [horizon + 1]

    for t in range(horizon):
        x, u, c = states[t], actions[t], costs[t]
        assert tf.reduce_all(states[t + 1] == solver.env.transition(x, u))
        assert c == solver.env.cost(x, u)

    assert costs[horizon] == solver.env.final_cost(states[horizon])


def test_solve(solver, initial_state, horizon):
    trajectory, iterations = solver.solve(initial_state, horizon)
    #assert iterations == 2
    print()
    print(trajectory)
