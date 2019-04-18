from __future__ import absolute_import, division, print_function, unicode_literals

import torch
import torch.jit
import numpy as np
import unittest
from common_utils import TestCase, run_tests, skipIfNotRegistered


def canonical(graph):
    return str(torch._C._jit_pass_canonicalize(graph))


def _quantize(x, scale, zero_point):
    """Quantizes a numpy array."""
    qx = np.round(x / scale).astype(np.uint8) + zero_point
    return qx


def _dequantize(qx, scale, zero_point):
    """Dequantizes a numpy array."""
    x = (qx - zero_point) * scale
    return x


@skipIfNotRegistered("Relu_ENGINE_DNNLOWP",
                     "fbgemm-based Caffe2 ops are not linked")
class TestQuantized(TestCase):
    def test_relu(self):
        a = (torch.tensor([4, 6, 1, 10], dtype=torch.uint8), 0.01, 5)
        r = torch.ops.c10.quantized_relu(a)
        np.testing.assert_equal(r[0].numpy(), torch.tensor([5, 6, 5, 10], dtype=torch.uint8).numpy())
        np.testing.assert_almost_equal(0.01, r[1])
        self.assertEqual(5, r[2])

    def test_quantize(self):
        a = (torch.tensor([4, 6, 1, 10], dtype=torch.uint8), 0.01, 5)
        r = torch.ops.c10.dequantize(a)
        np.testing.assert_almost_equal(r.numpy(), [-0.01, 0.01, -0.04, 0.05])
        # default args
        q_def = torch.ops.c10.quantize(r)
        # specified
        q = torch.ops.c10.quantize(r, scale=0.01, zero_point=5)
        np.testing.assert_equal(q[0].numpy(), a[0].numpy())
        np.testing.assert_almost_equal(q[1], a[1])
        self.assertEqual(q[2], a[2])

    def test_script(self):
        @torch.jit.script
        def foo(x):
            # type: (Tuple[Tensor, float, int]) -> Tuple[Tensor, float, int]
            return torch.ops.c10.quantized_relu(x)
        self.assertExpectedInline(canonical(foo.graph), '''\
graph(%x : (Tensor, float, int)):
  %1 : (Tensor, float, int) = c10::quantized_relu(%x)
  return (%1)
''')


class TestQuantizedOps(unittest.TestCase):
    """Tests the correctness of the quantized::relu op."""
    def test_qrelu(self):
        relu = torch.ops.aten.quantized_relu

        X = torch.arange(-5, 5, dtype=torch.float)
        scale = 2.0
        zero_point = 5
        qX = X.quantize_linear(scale=scale, zero_point=zero_point)

        Y = X.numpy().copy()
        Y[Y < 0] = 0
        qY = _quantize(Y, scale, zero_point)
        qY_hat = relu(qX)
        np.testing.assert_equal(qY, qY_hat.int_repr())


if __name__ == '__main__':
    run_tests()
