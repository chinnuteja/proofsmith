#include "wire_codec.h"

namespace orderd {
namespace {

void append_u16(std::vector<std::uint8_t>& out, std::uint16_t value) {
  out.push_back(static_cast<std::uint8_t>(value & 0xff));
  out.push_back(static_cast<std::uint8_t>((value >> 8) & 0xff));
}

void append_u64(std::vector<std::uint8_t>& out, std::uint64_t value) {
  for (int shift = 0; shift < 64; shift += 8) {
    out.push_back(static_cast<std::uint8_t>((value >> shift) & 0xff));
  }
}

bool read_u16(const std::uint8_t*& cursor, const std::uint8_t* end, std::uint16_t& value) {
  if (end - cursor < 2) return false;
  value = static_cast<std::uint16_t>(cursor[0] | (cursor[1] << 8));
  cursor += 2;
  return true;
}

bool read_u64(const std::uint8_t*& cursor, const std::uint8_t* end, std::uint64_t& value) {
  if (end - cursor < 8) return false;
  value = 0;
  for (int i = 0; i < 8; ++i) {
    value |= static_cast<std::uint64_t>(cursor[i]) << (8 * i);
  }
  cursor += 8;
  return true;
}

}  // namespace

std::vector<std::uint8_t> encode_order(const Order& order) {
  std::vector<std::uint8_t> out;
  out.reserve(8 + 2 + order.account.size() + 1 + 8 + 8);
  append_u64(out, order.id);
  append_u16(out, static_cast<std::uint16_t>(order.account.size()));
  out.insert(out.end(), order.account.begin(), order.account.end());
  out.push_back(order.side == Side::Sell ? 1 : 0);
  append_u64(out, static_cast<std::uint64_t>(order.price_ticks));
  append_u64(out, static_cast<std::uint64_t>(order.qty));
  return out;
}

bool decode_order(const std::uint8_t* data, std::size_t size, Order& out) {
  const std::uint8_t* cursor = data;
  const std::uint8_t* end = data + size;
  std::uint64_t id = 0;
  std::uint16_t account_len = 0;
  std::uint64_t price = 0;
  std::uint64_t qty = 0;
  if (!read_u64(cursor, end, id) || !read_u16(cursor, end, account_len)) return false;
  if (end - cursor < account_len + 1 + 8 + 8) return false;
  out.id = id;
  out.account.assign(reinterpret_cast<const char*>(cursor), account_len);
  cursor += account_len;
  const auto side = *cursor++;
  if (side > 1) return false;
  out.side = side == 1 ? Side::Sell : Side::Buy;
  if (!read_u64(cursor, end, price) || !read_u64(cursor, end, qty)) return false;
  out.price_ticks = static_cast<std::int64_t>(price);
  out.qty = static_cast<std::int64_t>(qty);
  return cursor == end;
}

}  // namespace orderd
