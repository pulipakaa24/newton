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
