export const number = (value, digits = 0) =>
  value.toLocaleString("ko-KR", { maximumFractionDigits: digits });
