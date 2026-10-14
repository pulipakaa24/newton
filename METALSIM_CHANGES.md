# MetalSim changes on this branch (`metalsim-1.5.2`)

Newton 1.5.2, the version Isaac Lab 3.0-EA pins, made to run on Apple silicon (Metal) with CUDA's semantics for
[MetalSim](https://github.com/pulipakaa24/MetalSim): Newton's implicit MPM solver (Isaac Lab 3.0-EA's only MPM) and
the rigid collision pipeline of Isaac Lab's Franka-Pour task at thousands of worlds. Every change keeps the CUDA and
CPU paths as they are; on Metal it either reproduces the previous result bit for bit or makes a run repeatable that
was not. MetalSim's `metalsim/physics/mpm/MPM.md` has the measurements and the verification.

This branch needs the MetalSim Warp fork ([pulipakaa24/warp](https://github.com/pulipakaa24/warp), branch
`metalsim`): device-side launch bounds (`wp.launch(..., dim_limit=)`), the Metal radix sort's `count_limit`,
deterministic mode on Metal and the per-kernel argument address space. With other Warp builds the code takes the
paths it took before (full launches, constant arguments). MetalSim installs it with `scripts/setup_newton152.sh`
into `.venv-newton152`.

Lineage: [newton-physics/newton](https://github.com/newton-physics/newton) tag `v1.5.2` (`cf5378db`) → this branch.
The branch is separate from `metalsim` (Newton 1.7.0.dev0, MetalSim's archived XPBD engine).

Licence: Apache License 2.0, as upstream. `LICENSE.md` is unchanged from newton-physics/newton (same blob). The
changes below modify Apache-2.0 code and are offered under the same licence.

## Commits (on top of `v1.5.2`)

| commit | change |
|---|---|
| `6f6075d1` | Colored Gauss-Seidel rheology kernels launch two blocks per GPU core on Metal (one 64-thread block per color before). Granular strain solve 390 -> 54 ms per frame (M4 Max); bitwise. |
| `00c24ef0` | Dense-grid bounds computed on the device on Metal (the host path ignored `particle_flags`, so the grid differed from CUDA's with inactive particles). |
| `a3fa1140` | Per-environment residual norms and system scaling use CUDA's 256-lane tile reductions on Metal. |
| `53a903d7` | Coupled MPM examples repeatable on Metal: MuJoCo Warp's NxN / SAP broadphase pairs stably sorted on the device (CUDA's thread order); `example_mpm_twoway_coupling` sums sand impulses per body in node order. |
| `da3ac2be` | Rheology solve bounded to the active nodes (`dim_limit` = the environment-first partition's active prefix) for rebuildable sparse grids. Franka-Pour MPM at 2,048 worlds 345 -> 239 ms per step; bitwise. |
| `0407977f` | Point warm-start gather / scatter as kernels that skip PIC null indices: an undersized sparse-grid reservation is reported as on CUDA instead of a segmentation fault on Metal. |
| `6d746225` | Proxy body wrenches (`coupling_harvest_proxy_wrenches`, Isaac Lab's coupler) summed per world in a fixed order on Metal: one result on every run (float atomics gave 20 different results in 20 calls at 2,048 worlds); same cost. |
| `9547400c` | HashTable insertion atomic on Metal (32-bit claim of the key's high word, then a 64-bit atomic min): concurrent inserts no longer overwrite each other, so the deterministic collision pipeline is repeatable. |
| `b430f593` | Deterministic contact reduction widens the contact id (up to 24 bits) for reducers above 2^20 contacts (2,048 Franka-Pour worlds produce 1.1-5 M triangle pairs per collide). |
| `8511b05d`, `77818cba` | Merges of the two lines above (`metalsim-mpm-scale`, `metalsim-rigid-det-sort`) on `53a903d7`. |
| `eac15793` | No 64-bit atomics Metal cannot make atomic: HashTable's 64-bit CAS stays off the Metal build (keys with bit 63 set are refused there); contact matching claims with an unsigned 64-bit minimum (same winner on every device). The Warp fork raises at launch for the refused forms. |
| `c1ab1cdc` | Colored Gauss-Seidel kernels read their arguments from device memory on Metal (Warp module option `metal_device_args`): granular 39.5 -> 34.6 ms per frame; bitwise. |
| `c0a98819` | Metal collision midphase: per-thread mesh-convex triangle overlaps (65 -> 0.26 ms per collide at 2,048 Franka worlds; same triangles) and four mesh threadgroups per GPU core. Collide 179 -> 82 ms (L4: 90 ms). |
| `555d6af8` | Barrier before each reset of the mesh-SDF kernels' shared `progress` counter: a thread still making its last loop check could re-enter the culling loop alone and pair its barriers with the wrong ones, which hung the GPU on Metal at 2,048 Franka worlds. Results unchanged whenever the race did not fire. |
| `1298fbbb` | 32 mesh threadgroups per GPU core on Metal (collide 80 -> 67 ms at 2,048 worlds), now that the race is fixed. |
| `ddb015b9` | Deterministic mode on Metal sorts and gathers only the active contacts (key preparation with `dim_limit`, radix sort with `count_limit`): sort 12.4 -> 0.2 ms, deterministic collide 192.6 -> 68.3 ms at 2,048 worlds. |
| `35791a07` | `METALSIM_CHANGES.md`. |
| `3813cbba` | Kamino metric argmax keys (63-bit) without 64-bit exchange on Metal (the Warp fork refuses it at launch, so the EoM / kinematics / joint / limit metric kernels did not run there): per-thread key scratch, per-world 64-bit max of (value rank, ~thread), a finalize launch per metric kernel; the key of the maximum, lowest thread on ties. CPU / CUDA keep the exchange. Same protocol as on `metalsim` (1.7). |
| `e0c7c82e` | HashTable's Metal claim loop bounded (probes plus 65,536 passes, then -1 as for a full table, counted in `ht_insert_failures`): Apple GPUs give no forward-progress guarantee, so no thread may wait without bound for a claimant. |
| `c0427fc7` | `METALSIM_CHANGES.md` rows for `3813cbba` and `e0c7c82e`. |
| `27415f95` | Metal: the rigidity operator (`J`, `IJtm`) is assembled from its kept triplet slots only (moved to the front in slot order, count passed to `bsr_set_from_triplets`; the stable sort orders them as before, so the matrices are the same). Franka-Pour MPM at 2,048 worlds: collider compliance 6.4 -> 3.1 ms of GPU time per step; bitwise. `NEWTON_METAL_RIGIDITY_COMPACT=0` restores the full assembly. |
| `80e79684` | Metal: in the rheology loop the two rigidity products run only on the rows with blocks (listed on the device, launch bounded by the list length with an in-kernel guard): an empty row's result is a fixed point once the initial guess applied the full product, so every value is the same. From 8,192 rows (`NEWTON_METAL_LISTED_ROWS_MIN`); `NEWTON_METAL_LISTED_ROWS_MV=0` restores the full products. Franka-Pour 2,048 worlds: 8.8 -> 2.6 ms of GPU time per step; bitwise (1 / 64 / 2,048 worlds, eager and captured). |
| `3fd1f052` | `METALSIM_CHANGES.md` rows for `27415f95` and `80e79684`. With the Warp fork's `8631b6b0` and `fddebdbd`: Franka-Pour MPM captured step at 2,048 worlds 90.5-91.2 -> 78.9-79.0 ms, Franka-Pour policy step (2,048 envs, M4 Max) 2.06 -> 1.81 s. |
| this commit | Gauss-Seidel coloring with separate worlds (`Config.separate_worlds`, discontinuous strain bases such as P0): the color blocks were `cell * nodes_per_cell`, but environment-first strain partitions number a cell's nodes in environment-major order, so on a sparse multi-environment grid the blocks were a permutation of other cells' nodes and strain nodes solved concurrently in one color shared velocity nodes (a data race: two identical runs differed from the first step on Metal; the coloring is equally invalid on CUDA). Blocks now start at the partition index of the cell's first node (`make_partition_color_block_indices_kernel`); single-environment grids keep the previous kernel (bitwise unchanged); Jacobi solves (Isaac Lab's Franka-Pour) never color. Checked by MetalSim's `metalsim/physics/mpm/probes/gs_coloring_check.py` (no write conflicts within a color, every strain node once per sweep). |
| this commit | Metal: in the rheology loop, a rigidity product whose rows `warp.sparse.bsr_mv` would sum with its tiled kernel goes through `bsr_mv` itself instead of the listed-rows kernel. These are the body rows of IJtm: one block per collider node of the body. With the Warp fork's `metal_bsr_mv_tiles`, that is CUDA's kernel and summation order. The J product, with one row per grid node, keeps the listed rows. `example_mpm_twoway_coupling`: IJtm (12 rows, up to about 1,170 blocks each) went from 29-40 to 12.1-12.9 ms per 50 calls. Late in the run, the GPU kernel sum per frame went from 55.3 to 36.4 ms. Without that Warp option, the product is unchanged (listed rows, bitwise as before). |

`c0a98819` … `ddb015b9` were written on top of `eac15793` (as `de978b55`, `7beedf43`, `0013572a`, `ced01724`) and
cherry-picked onto `c1ab1cdc` unchanged; the resulting tree is the union of both lines.

The upstream `v1.5.2` behaviour (MetalSim's MPM "oracle") remains reachable: every change above is either Metal-only
or bitwise on the tested scenes, and `scripts/setup_newton152.sh` installs stock `v1.5.2` with
`METALSIM_NEWTON152_REPO=https://github.com/newton-physics/newton METALSIM_NEWTON152_REF=v1.5.2`.
