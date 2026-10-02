# Excluded from scored runs

These instances stay in the Track B set and on the Track B page. No scored run calls the model on them.

## httplib-2492

This build turns mbedTLS and OpenSSL off, so the buggy destructor is not compiled, and the issue text contains the suggested fix.
