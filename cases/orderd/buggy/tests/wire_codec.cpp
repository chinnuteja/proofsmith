#include "wire_codec.h"

#include <iostream>

namespace {

int g_fails = 0;

void check(bool cond, const char* text) {
  if (!cond) {
    std::cerr << "FAIL " << text << "\n";
    ++g_fails;
  }
}

}  // namespace

int main() {
  orderd::Order order{42, "carol", orderd::Side::Sell, 19, 7};
  const auto bytes = orderd::encode_order(order);
  orderd::Order decoded;
  check(orderd::decode_order(bytes.data(), bytes.size(), decoded), "decode full buffer");
  check(decoded.id == order.id, "id");
  check(decoded.account == order.account, "account");
  check(decoded.side == order.side, "side");
  check(decoded.price_ticks == order.price_ticks, "price");
  check(decoded.qty == order.qty, "qty");
  check(!orderd::decode_order(bytes.data(), 4, decoded), "short buffer rejected");
  orderd::Order buy{7, "d", orderd::Side::Buy, 1, 1};
  const auto buy_bytes = orderd::encode_order(buy);
  orderd::Order buy_decoded;
  check(orderd::decode_order(buy_bytes.data(), buy_bytes.size(), buy_decoded), "decode buy");
  check(buy_decoded.side == orderd::Side::Buy, "buy side");
  return g_fails == 0 ? 0 : 1;
}
