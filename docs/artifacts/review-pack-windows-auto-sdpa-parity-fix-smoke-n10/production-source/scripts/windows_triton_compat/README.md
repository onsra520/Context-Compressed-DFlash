# Windows Triton metadata bridge

AutoAWQ 0.2.9 declares a dependency on the `triton` distribution, whose 3.7.1
release has no Windows wheel. The compatible Windows implementation is
`triton-windows==3.7.1.post27`, which provides the same `triton` import module
under a different distribution name.

This metadata-only package is installed after `triton-windows`. It owns no
Python modules and exists only so package metadata accurately records that the
AutoAWQ dependency is supplied by the pinned Windows implementation.
