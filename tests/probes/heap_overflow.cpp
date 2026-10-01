// The write is one past new int[8]. It lives in a separate function so
// UBSan's object-size check does not see the allocation bound and abort
// before ASan reports heap-buffer-overflow. With -fno-sanitize-recover=undefined
// a direct a[8] = 1 in main is reported as UBSan, not ASan.
__attribute__((noinline, optnone)) void poke(int* p, int index) { p[index] = 1; }

int main() {
  int* a = new int[8];
  poke(a, 8);
  return 0;
}
