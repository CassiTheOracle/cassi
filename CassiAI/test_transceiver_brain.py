"""Focused tests for the recurrent transceiver brain."""

import torch
from cassi.transceiver_brain import TransceiverBrain, TransceiverNeuron


def test_neuron_is_recurrent():
    n = TransceiverNeuron(width=16, theta_init=0.5)
    x = torch.randn(2, 16)
    out1 = n(x)
    out2 = n(x)
    assert out1.shape == (2, 16)
    assert not torch.allclose(out1, out2), "recurrent neuron produced identical outputs"
    assert n.h.shape == (2, 16)
    assert n.h_prev.shape == (2, 16)
    n.reset_state(batch_size=4)
    assert n.h.shape == (4, 16)
    assert n.h_prev.shape == (4, 16)


def test_neuron_gradients_flow():
    n = TransceiverNeuron(width=8, theta_init=0.5)
    x = torch.randn(1, 8)
    out = n(x)
    loss = out.sum()
    loss.backward()
    assert n.theta.grad is not None
    assert n.b0.grad is not None
    assert n.b1.grad is not None
    assert n.emit_gain.grad is not None


def test_brain_sequence_unroll():
    brain = TransceiverBrain(D=1040, n_neurons=16, use_homeostasis=False)
    seq = torch.randn(2, 8, 1040)
    brain.reset_state(batch_size=2)
    out = brain(seq)
    assert out.shape == (2, 8, 1024)
    stats = brain.get_field_stats()
    assert stats['energy'] >= 0
    assert len(brain.get_neuron_freqs()) == 16


def test_brain_backward_compatible_2d():
    brain = TransceiverBrain(D=1040, n_neurons=8, use_homeostasis=False)
    x = torch.randn(3, 1040)
    brain.reset()
    out = brain(x)
    assert out.shape == (3, 1024)





def test_qi_pathway():
    """Qi is computed from prediction error and Yin correction modifies the field."""
    brain = TransceiverBrain(D=1040, n_neurons=16, use_homeostasis=False)
    brain.reset_state(batch_size=2)
    x = torch.randn(2, 1040)
    target = torch.randn(2, 1024)

    # Take field snapshot before Qi
    out = brain._step(x, use_neurons=True, target=target)
    assert out.shape == (2, 1024)
    assert brain._qi_energy.item() > 0, "qi_energy should be positive"
    assert 0.0 <= brain._qi_bias.item() <= 1.0, f"qi_bias in [0,1], got {brain._qi_bias.item()}"
    assert 0.5 <= brain.lr_modulation <= 2.0, f"lr_mod in [0.5,2.0], got {brain.lr_modulation}"
    qi_state = brain.qi_state
    assert qi_state in ('fire', 'wood', 'earth', 'metal', 'water'), f"invalid qi_state: {qi_state}"


def test_qi_no_target():
    """Without target, Qi is not computed and the forward path still works."""
    brain = TransceiverBrain(D=1040, n_neurons=8, use_homeostasis=False)
    brain.reset_state(batch_size=2)
    out = brain._step(torch.randn(2, 1040), use_neurons=True, target=None)
    assert out.shape == (2, 1024)


def test_qi_3d_target():
    """3-D forward passes per-timestep targets through to each _step."""
    brain = TransceiverBrain(D=1040, n_neurons=8, use_homeostasis=False)
    brain.reset_state(batch_size=2)
    seq = torch.randn(2, 4, 1040)
    targets = torch.randn(2, 4, 1024)
    out = brain.forward(seq, target=targets)
    assert out.shape == (2, 4, 1024)
    # Qi should have been computed for all 4 timesteps
    assert brain._qi_energy.item() > 0


def test_yin_correction_modifies_field():
    """Yin correction contract the field toward correct state."""
    brain = TransceiverBrain(D=1040, n_neurons=8, use_homeostasis=False)
    brain.reset_state(batch_size=1)
    x = torch.randn(1, 1040)
    target = torch.randn(1, 1024)

    # Field without Yin correction
    brain_no_yin = TransceiverBrain(D=1040, n_neurons=8, use_homeostasis=False)
    brain_no_yin.load_state_dict(brain.state_dict(), strict=False)
    brain_no_yin.reset_state(batch_size=1)
    out_no_yin = brain_no_yin._step(x, use_neurons=True, target=None)
    field_no_yin = brain_no_yin.field.clone()

    # Field with Yin correction (target given)
    out_with_yin = brain._step(x, use_neurons=True, target=target)
    field_with_yin = brain.field.clone()

    # Yin correction should change the field relative to forward-only
    assert not torch.allclose(field_with_yin, field_no_yin, atol=1e-6), \
        "Yin correction should modify the field"



if __name__ == "__main__":
    test_neuron_is_recurrent()
    test_neuron_gradients_flow()
    test_brain_sequence_unroll()
    test_brain_backward_compatible_2d()
    test_qi_pathway()
    test_qi_no_target()
    test_qi_3d_target()
    test_yin_correction_modifies_field()
    print("transceiver brain tests PASSED")
