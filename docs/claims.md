# Claims ledger. Only entries marked VERIFIED may be stated in any output.

## C1 VERIFIED — homepage headline
URL: https://byteask.ai/ (fetched 2026-10-01)
Quote: "Writes C++. Proves it compiles, runs, and passes."

## C2 VERIFIED — homepage gdb demo is an order-book deadlock fixed with scoped_lock
URL: https://byteask.ai/ (fetched 2026-10-01)
Quote: "my gdb is stopped on the deadlock in orderd, take a look" / "#3 OrderBook::cancel (...) at order_book.cpp:214" / "p risk_mtx_._M_mutex.__data.__owner ... (held by the risk thread)" / "+ std::scoped_lock lk(book_mtx_, risk_mtx_);"

## C3 VERIFIED — homepage Evidence section shows tests passing on a tree with an ASan bug
URL: https://byteask.ai/ (fetched 2026-10-01)
Quote: "AddressSanitizer: heap-buffer-overflow ... in OrderBook::cancel_all()" and "ctest on the same tree, same run." with "100% tests passed, 0 tests failed out of 3" (book_ops, risk_engine, wire_codec)

## C4 VERIFIED — ByteAsk connects MCP servers
URL: https://docs.byteask.ai/docs/overview (fetched 2026-10-01)
Quote: "MCP servers | Connect any Model Context Protocol server"

## C5 VERIFIED — headless mode
URL: https://docs.byteask.ai/docs/overview (fetched 2026-10-01)
Quote: "Non-interactive mode | Scripting-friendly `exec` subcommand with JSONL output"

## C6 VERIFIED — built-in sanitizer and rr tools
URL: https://docs.byteask.ai/docs/features (fetched 2026-10-01)
Quote: "`cpp_sanitize` | Build and run with ASan, UBSan, TSan, or Valgrind" and "`debug_record` | Record and replay a deterministic trace with rr"

## U1 UNVERIFIED — hiring page: patch correctness is an open problem; "knowing when the honest answer is 'we don't know'"
## U2 UNVERIFIED — CEO rule: "use AI to write the deterministic tool"
## U3 UNVERIFIED — CTO owns harness, benchmarks and model training
## U4 UNVERIFIED — Multi-SWT-Bench figures (126 C++ instances, 52.5%, ~994K LoC)
