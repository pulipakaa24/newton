# SPDX-FileCopyrightText: Copyright (c) 2026 The Newton Developers
# SPDX-License-Identifier: Apache-2.0

import types
import unittest

import numpy as np
import warp as wp

from newton._src.solvers.mujoco import ordered_broadphase


def _metal_device():
    for device in wp.get_devices():
        if getattr(device, "is_metal", False):
            return device
    return None


@unittest.skipIf(_metal_device() is None, "needs a Metal device")
class TestMujocoOrderedBroadphase(unittest.TestCase):
    def test_pairs_sorted_into_nxn_thread_order(self):
        """Sort an atomically appended pair list into the NxN broadphase's thread order.

        The pairs arrive in a scrambled order, some with geoms swapped (MuJoCo Warp orders a pair
        by geom type), and the tail past ``ncollision`` must stay untouched.
        """
        device = _metal_device()
        rng = np.random.default_rng(0)
        nworld, ngeom, naconmax = 3, 12, 64
        g1, g2 = np.triu_indices(ngeom, k=1)
        candidates = [(w, a, b) for w in range(nworld) for a, b in zip(g1, g2, strict=True)]
        chosen = sorted(rng.choice(len(candidates), size=40, replace=False))
        expected = [candidates[i] for i in chosen]  # thread order: world-major, then triu order

        scrambled = [expected[i] for i in rng.permutation(len(expected))]
        pair = np.full((naconmax, 2), -7, dtype=np.int32)
        pairid = np.full((naconmax, 2), -7, dtype=np.int32)
        worldid = np.full(naconmax, -7, dtype=np.int32)
        for slot, (w, a, b) in enumerate(scrambled):
            pair[slot] = (b, a) if (a + b) % 3 == 0 else (a, b)
            pairid[slot] = (-1, 1000 * w + 50 * a + b)
            worldid[slot] = w

        ctx = types.SimpleNamespace(
            collision_pair=wp.array(pair, dtype=wp.vec2i, device=device),
            collision_pairid=wp.array(pairid, dtype=wp.vec2i, device=device),
            collision_worldid=wp.array(worldid, dtype=int, device=device),
        )
        d = types.SimpleNamespace(
            naconmax=naconmax, nworld=nworld, ncollision=wp.array([len(expected)], dtype=int, device=device)
        )
        m = types.SimpleNamespace(ngeom=ngeom)
        ordered_broadphase.order_collision_pairs(m, d, ctx)

        out_pair = ctx.collision_pair.numpy()
        out_pairid = ctx.collision_pairid.numpy()
        out_world = ctx.collision_worldid.numpy()
        n = len(expected)
        got = [(int(w), int(min(p)), int(max(p))) for w, p in zip(out_world[:n], out_pair[:n], strict=True)]
        self.assertEqual(got, expected)
        np.testing.assert_array_equal(out_pairid[:n, 1], [1000 * w + 50 * a + b for w, a, b in expected])
        for (_w, a, b), p in zip(expected, out_pair[:n], strict=True):
            self.assertEqual(tuple(p), (b, a) if (a + b) % 3 == 0 else (a, b))  # geom order within a pair kept
        np.testing.assert_array_equal(out_pair[n:], pair[n:])
        np.testing.assert_array_equal(out_world[n:], worldid[n:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
