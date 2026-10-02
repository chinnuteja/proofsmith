Oracle: AddressSanitizer and UndefinedBehaviorSanitizer, built together. Call finish with variant asan_ubsan.

Drive the exact API sequence that makes the project read or write freed or out-of-bounds memory, or hit UB (signed overflow, shift, misaligned or null access). Keep the harness deterministic.

Hold a returned reference or pointer across the later call that frees or reallocates it. Copying the value out before that call hides a lifetime bug. For a numeric result that becomes wrong on extreme inputs, call the function with those inputs so the overflow happens inside the project, not in the harness.

A harness that makes an overflow obvious to the compiler can get a UBSan object-size report instead of ASan. Undefined behavior is not recovered from, so that report stops the process before AddressSanitizer runs. Do not write the out-of-bounds store in the same function that can see the allocation bound.
