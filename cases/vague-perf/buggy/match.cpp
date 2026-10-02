#include "match.h"

bool contains_text(const std::string& text, const std::string& needle) {
  if (needle.empty()) {
    return true;
  }
  return text.find(needle) != std::string::npos;
}
