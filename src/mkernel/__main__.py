"""MKernel: A Jupyter Kernel for Matlab

package execution module, used with `python -m mkernel`

Copyright © 2023 Carsten Allefeld
SPDX-License-Identifier: GPL-3.0-or-later
"""


from ipykernel.kernelapp import IPKernelApp

from .kernel import MKernel


IPKernelApp.launch_instance(kernel_class=MKernel)
