#pragma once

#include <cstddef>
#include <string>
#include <unordered_map>

class PriceCache {
 public:
  explicit PriceCache(std::size_t capacity);
  ~PriceCache();
  PriceCache(const PriceCache&) = delete;
  PriceCache& operator=(const PriceCache&) = delete;

  void put(const std::string& symbol, double price);
  const double& get(const std::string& symbol);

 private:
  struct Node {
    std::string symbol;
    double price;
    Node* newer;
    Node* older;
  };

  void detach(Node* node);
  void push_front(Node* node);
  void evict();

  std::size_t capacity_;
  Node* newest_;
  Node* oldest_;
  std::unordered_map<std::string, Node*> index_;
};
