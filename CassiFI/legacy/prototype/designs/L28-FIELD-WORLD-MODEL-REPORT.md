# CassiQwen L28—field world-model identification report

- Verdict: **SUPPORTS**
- Board schema: `cassi.l28.field-world-model.v1`
- Board status: `COMPLETE`
- Mode layout: `cassi.modal.native-linear-x-fast.v1`
- Operator profile: `cassi.modal.recurrence.v1`
- World fingerprint: `cb48ad10666bc5d6e423524e0a763f026c26768f55623ea1417cff67e44dbc58`
- Manifest SHA-256: `eba97f3284f8acb9cb410a4df5510e69fd76d482d643e25def8a70dac779b098`

## Metrics

| Arm | Parameters | Train MSE | Validation MSE | Test MSE |
|---|---:|---:|---:|---:|
| `field` | 163 | 6.29336371e-06 | 6.273244445e-06 | 7.560723674e-06 |
| `stateless` | 123 | 0.1889019695 | 0.2092242492 | 0.194394921 |
| `gru` | 159 | 0.02592202875 | 0.03454577696 | 0.04015505893 |
| `field-reset` | 163 | — | — | 0.1875741906 |
| `field-shuffled` | 163 | — | — | 0.2255896609 |

## Mechanical checks

- finite trajectory: `True`
- finite generated data: `True`
- maximum absolute observation: `4.21212101`
- maximum absolute target: `2.255120993`
- maximum absolute state: `2.409029484`
- maximum field power: `0.2438177913`
- duplicate training digest match: `True`
- checkpoint SHA-256: `c6947358ebfe8f55592975dc39981afa046f21b877a2c508a5341f36d8c69b43`

## Decision

- held-out field arm and both temporal ablations satisfy the frozen thresholds

This board is an offline field-system identification result. It does not establish language quality, multimodal understanding, Qwen intervention benefit, live engine authority, or production adoption.
