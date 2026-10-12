# MetalSim changes on this branch (`metalsim`)

XPBD solver fixes made while validating Newton as an alternative physics engine for
[MetalSim](https://github.com/pulipakaa24/MetalSim) on Apple silicon (see "What was built where" in its
[README](https://github.com/pulipakaa24/MetalSim/blob/main/README.md)). MetalSim's Newton XPBD path is archived as
experimental: it trains about 1.6x faster than MuJoCo Warp on the G1 task but its joints are looser than PhysX's,
so MuJoCo Warp is MetalSim's parity engine. This branch is kept so the measurements can be reproduced.

Lineage: [newton-physics/newton](https://github.com/newton-physics/newton) `main` at `45458023` → this branch.

Licence: Apache License 2.0, as upstream. `LICENSE.md` is unchanged from newton-physics/newton (same blob). The
changes below modify Apache-2.0 code and are offered under the same licence.

## Commits (on top of `45458023`)

| commit | change |
|---|---|
| `f844a4e6` | Revolute (hinge) angles that cross ±π no longer get a ~2π limit correction (limit ranges beyond ±π exploded). |
| `fda6658a` | Joint relaxation applied consistently to the linear and angular parts (the defaults gave 1.36x torque and 0.78x gravity on a pendulum); in-solver PD joint drives whose stiffness does not depend on the iteration count. |
| `9f626ce2` | Joint colouring (parallel joint solve) and exact per-body contact forces. |
| `9b0901d3` | PD drive damping on light, heavily damped links. |
| `02799d8f` | Drive rows moved out of `solve_body_joints`. |
| `6476ac46` | Matrix-vector products in the drive rows. |
| `fcc1505d` | Drive kernels skipped when no joint has a drive; angle references baked. |
| `742a7759` | All drive-capable joints covered under an explicit drive mode. |
| `242eeda7` | Drive force reported per DOF. |
| `90e23324` | Fast path for PD drive rows on hinges. |

| `fb95e095` | `METALSIM_CHANGES.md`. |
| `d06b2c02` | HashTable insertion atomic on Metal (Metal has no 64-bit compare-and-swap and Warp lowered `atomic_cas` on 64-bit keys to a plain read-modify-write: concurrent inserts of the contact-reduction table overwrote each other, so contacts changed from run to run). A slot is claimed with a 32-bit compare-and-swap on the key's high word, then the key is published with a 64-bit atomic min; CPU and CUDA keep the original code. |
| `7d80b8a5` | No 64-bit atomics Metal cannot make atomic: the 64-bit CAS moves into a native helper that is not compiled for Metal (keys with bit 63 set are refused there; Newton's keys never set it); contact matching claims with an unsigned 64-bit minimum (same winner on every device). Needed with the Warp fork's `metalsim` branch from `c1bb061b` on, which raises at launch for the refused atomics instead of running them non-atomically (the rough G1 task otherwise fails in `reduce_buffered_contacts_kernel`). |
| this commit | `METALSIM_CHANGES.md` rows for the two commits above. |

`d06b2c02` and `7d80b8a5` are `299d5432` and `33f4783a` (written on `90e23324`) cherry-picked unchanged. The same
two fixes on upstream `45458023` itself (the Newton that MetalSim's `newton` extra installs into `.venv`) are branch
`metalsim-hashtable-metal`, `24fb5367`. In the G1 rough task at 4,096 worlds the stock table listed 221 K duplicate
slots and lost 104 K keys per collide on Metal; the fixed one none (MetalSim, 2026-10-11).

This branch defaults to `joint_drive_mode="pd"`; upstream's compliance drive stays available.

## Upstream

The three defects are filed on newton-physics/newton as issues
[#4313](https://github.com/newton-physics/newton/issues/4313),
[#4314](https://github.com/newton-physics/newton/issues/4314) and
[#4315](https://github.com/newton-physics/newton/issues/4315), with pull requests
[#4316](https://github.com/newton-physics/newton/pull/4316) (branch `fix/xpbd-revolute-angle-wrap`),
[#4317](https://github.com/newton-physics/newton/pull/4317) (`fix/xpbd-joint-relaxation`) and
[#4318](https://github.com/newton-physics/newton/pull/4318) (`feat/xpbd-pd-joint-drive`, stacked on the other two).
The pull-request branches are clean rewrites of the fixes above against upstream `main`, without the
MetalSim-specific options; PR #4316 also fixes a small-swing rescale that this branch does not carry. As of
2026-09-25 all six are open, awaiting the contributor licence agreement and maintainer review.
