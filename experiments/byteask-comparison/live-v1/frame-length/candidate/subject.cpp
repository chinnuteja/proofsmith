#include "subject.h"
bool complete_frame(const std::vector<std::uint8_t>& bytes) {
  if (bytes.size() < 4) return false;
  std::uint32_t length = (std::uint32_t(bytes[0]) << 24) | (std::uint32_t(bytes[1]) << 16)
                       | (std::uint32_t(bytes[2]) << 8) | bytes[3];
  return bytes.size() - 4 >= static_cast<std::size_t>(length);
}
