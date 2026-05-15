# TT_EMULE Setup

Setting up with https://github.com/tenstorrent/tt-emule/blob/main/GETTING_STARTED.md:

### Erroneous Build command

The build command listed does not generate the binaries for the unit_tests_api. This build command worked for me:
```
cmake -B build_emule -G Ninja \
  -DCMAKE_C_COMPILER=clang-20 -DCMAKE_CXX_COMPILER=clang++-20 \
  -DTT_METAL_USE_EMULE=ON \
  -DTT_METAL_EMULATION=ON \
  -DTT_METAL_BUILD_TESTS=ON \
  -DTTNN_BUILD_TESTS=ON \
  -DTT_EMULE_PATH="$ROOT/tt-emule" \
  -DTT_INSTALL=OFF
  ```

After the build succeeded with this command and running the regression test, I was seeing 19 passes, 124 failed. I cleaned the build and ran it again, and saw 131 passes, 12 failed.

### env vars

Leaving these here for quick access, since the exact commands aren't copy-pastable in the original document.

`export CLUSTER_DESCS="$ROOT/tt-metal/tt_metal/third_party/umd/tests/cluster_descriptor_examples"`
`export TT_METAL_EMULE_MODE=1 TT_METAL_SLOW_DISPATCH_MODE=1`
`export TT_METAL_MOCK_CLUSTER_DESC_PATH="$CLUSTER_DESCS/wormhole_N150.yaml"`
