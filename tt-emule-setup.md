# TT_EMULE Setup

Setting up with https://github.com/tenstorrent/tt-emule/blob/main/GETTING_STARTED.md:

### Mistake #1: Build command

The build command listed does not generate the binaries for the unit_tests_api. This build command worked for me:
```
cmake -B build_emule -G Ninja \
  -DCMAKE_C_COMPILER=clang-20 -DCMAKE_CXX_COMPILER=clang++-20 \
  -DCMAKE_AR=/usr/bin/llvm-ar-20 -DCMAKE_RANLIB=/usr/bin/llvm-ranlib-20 \
  -DCMAKE_BUILD_TYPE=Release \
  -DTT_METAL_USE_TT_EMULE=ON \
  -DTT_METAL_EMULATION=ON \
  -DTT_METAL_BUILD_TESTS=ON \
  -DTTNN_BUILD_TESTS=ON \
  -DTT_EMULE_PATH="$ROOT/tt-emule" \
  -DENABLE_TRACY=OFF \
  -DTT_INSTALL=OFF
  ```

After the build succeeded with this command and running the regression test, I was seeing 19 passes, 124 failed. I cleaned the build and ran it again, and saw 131 passes, 12 failed.

### Mistake #2: env vars

The tutorial mentions setting env vars at step 4, however these are needed when building at step 3 so these should be moved to before the build command at step 3.
