# SPDX-FileCopyrightText: Copyright (c) 2026 The Newton Developers
# SPDX-License-Identifier: Apache-2.0

"""Thread-ordered MuJoCo Warp broadphase pair lists on Metal.

MuJoCo Warp's broadphase appends each overlapping geom pair to ``collision_pair`` through an atomic
counter. The narrowphase then writes contacts in pair-list order, and constraint rows follow the
contact order, so the pair order reaches every solver sum. On CUDA a small launch's warps reach the
counter in launch order, which gives the pair list in thread order run after run. On Metal the
SIMD-groups of a launch reach it in varying order, so the pair list (and the whole step after it)
differs between identical runs.

:func:`install` wraps MuJoCo Warp's NxN and SAP broadphases so that, on Metal, the emitted pairs are
stably sorted by ``(world, min(geom), max(geom))``. The NxN pair list is ``numpy.triu_indices``
order, so for the NxN broadphase this is exactly the thread order of its launch (CUDA's order).
"""

from __future__ import annotations

import warp as wp

_INSTALLED_ATTR = "_newton_ordered_broadphase"


@wp.kernel
def _pair_sort_keys(
    ngeom: int,
    naconmax: int,
    pad_key: wp.int64,
    ncollision: wp.array[int],
    collision_pair: wp.array[wp.vec2i],
    collision_worldid: wp.array[int],
    keys: wp.array[wp.int64],
    values: wp.array[int],
):
    i = wp.tid()
    n = wp.min(ncollision[0], naconmax)
    key = pad_key
    if i < n:
        g = collision_pair[i]
        g_lo = wp.int64(wp.min(g[0], g[1]))
        g_hi = wp.int64(wp.max(g[0], g[1]))
        key = (wp.int64(collision_worldid[i]) * wp.int64(ngeom) + g_lo) * wp.int64(ngeom) + g_hi
    keys[i] = key
    values[i] = i


@wp.kernel
def _pair_gather(
    naconmax: int,
    ncollision: wp.array[int],
    order: wp.array[int],
    pair_in: wp.array[wp.vec2i],
    pairid_in: wp.array[wp.vec2i],
    worldid_in: wp.array[int],
    pair_out: wp.array[wp.vec2i],
    pairid_out: wp.array[wp.vec2i],
    worldid_out: wp.array[int],
):
    i = wp.tid()
    if i < wp.min(ncollision[0], naconmax):
        src = order[i]
        pair_out[i] = pair_in[src]
        pairid_out[i] = pairid_in[src]
        worldid_out[i] = worldid_in[src]


_SCRATCH: dict = {}


def _scratch(device, naconmax: int):
    """Per-device sort and copy buffers (grow-only; captured graphs keep referencing them)."""
    key = (device.alias, naconmax)
    buf = _SCRATCH.get(key)
    if buf is None:
        buf = (
            wp.empty(2 * naconmax, dtype=wp.int64, device=device),
            wp.empty(2 * naconmax, dtype=int, device=device),
            wp.empty(naconmax, dtype=wp.vec2i, device=device),
            wp.empty(naconmax, dtype=wp.vec2i, device=device),
            wp.empty(naconmax, dtype=int, device=device),
        )
        _SCRATCH[key] = buf
    return buf


def order_collision_pairs(m, d, ctx) -> None:
    """Stably sort the broadphase pair list of ``ctx`` by ``(world, min(geom), max(geom))`` on the device."""
    naconmax = d.naconmax
    if naconmax == 0:
        return
    device = ctx.collision_pair.device
    ngeom = int(m.ngeom)
    pad_key = int(d.nworld) * ngeom * ngeom  # one past the largest real key
    end_bit = max(pad_key.bit_length(), 1)
    keys, values, pair_tmp, pairid_tmp, worldid_tmp = _scratch(device, naconmax)

    wp.launch(
        _pair_sort_keys,
        dim=naconmax,
        inputs=[ngeom, naconmax, pad_key, d.ncollision, ctx.collision_pair, ctx.collision_worldid],
        outputs=[keys, values],
        device=device,
    )
    wp.utils.radix_sort_pairs(keys, values, naconmax, end_bit=end_bit)
    wp.copy(pair_tmp, ctx.collision_pair, count=naconmax)
    wp.copy(pairid_tmp, ctx.collision_pairid, count=naconmax)
    wp.copy(worldid_tmp, ctx.collision_worldid, count=naconmax)
    wp.launch(
        _pair_gather,
        dim=naconmax,
        inputs=[naconmax, d.ncollision, values, pair_tmp, pairid_tmp, worldid_tmp],
        outputs=[ctx.collision_pair, ctx.collision_pairid, ctx.collision_worldid],
        device=device,
    )


def install() -> None:
    """Order MuJoCo Warp's broadphase output on Metal devices (idempotent; other devices are untouched)."""
    from mujoco_warp._src import collision_driver

    if getattr(collision_driver, _INSTALLED_ATTR, False):
        return

    def _wrap(broadphase):
        def ordered(m, d, ctx, awake_prev=None):
            broadphase(m, d, ctx, awake_prev)
            if getattr(ctx.collision_pair.device, "is_metal", False):
                order_collision_pairs(m, d, ctx)

        ordered.__name__ = broadphase.__name__
        ordered.__doc__ = broadphase.__doc__
        return ordered

    # collision() looks both functions up as module globals at call time.
    collision_driver.nxn_broadphase = _wrap(collision_driver.nxn_broadphase)
    collision_driver.sap_broadphase = _wrap(collision_driver.sap_broadphase)
    setattr(collision_driver, _INSTALLED_ATTR, True)
