#include "price_cache.h"

PriceCache::PriceCache(std::size_t capacity)
    : capacity_(capacity), newest_(nullptr), oldest_(nullptr) {}

PriceCache::~PriceCache() {
  Node* node = newest_;
  while (node != nullptr) {
    Node* older = node->older;
    delete node;
    node = older;
  }
}

void PriceCache::detach(Node* node) {
  if (node->newer != nullptr) {
    node->newer->older = node->older;
  } else {
    newest_ = node->older;
  }
  if (node->older != nullptr) {
    node->older->newer = node->newer;
  } else {
    oldest_ = node->newer;
  }
  node->newer = nullptr;
  node->older = nullptr;
}

void PriceCache::push_front(Node* node) {
  node->newer = nullptr;
  node->older = newest_;
  if (newest_ != nullptr) {
    newest_->newer = node;
  }
  newest_ = node;
  if (oldest_ == nullptr) {
    oldest_ = node;
  }
}

void PriceCache::evict() {
  Node* victim = oldest_;
  if (victim == nullptr) {
    return;
  }
  detach(victim);
  index_.erase(victim->symbol);
  delete victim;
}

void PriceCache::put(const std::string& symbol, double price) {
  auto found = index_.find(symbol);
  if (found != index_.end()) {
    Node* node = found->second;
    node->price = price;
    detach(node);
    push_front(node);
    return;
  }
  if (capacity_ == 0) {
    return;
  }
  if (index_.size() >= capacity_) {
    evict();
  }
  Node* node = new Node{symbol, price, nullptr, nullptr};
  index_.emplace(symbol, node);
  push_front(node);
}

const double& PriceCache::get(const std::string& symbol) {
  auto found = index_.find(symbol);
  if (found == index_.end()) {
    static double missing = 0.0;
    return missing;
  }
  Node* node = found->second;
  detach(node);
  push_front(node);
  return node->price;
}
