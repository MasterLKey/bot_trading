import { createContext, useContext } from "react";

export const MarketContext = createContext("equities");

export function useMarket() {
  return useContext(MarketContext);
}

export function marketQuery(market) {
  return `market=${encodeURIComponent(market)}`;
}
