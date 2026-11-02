const nf = (digits: number) => new Intl.NumberFormat("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const int = (v: number) => new Intl.NumberFormat("en-GB").format(Math.round(v));
export const fixed = (v: number, digits = 2) => nf(digits).format(v);
export const share = (v: number, digits = 1) => `${nf(digits).format(100 * v)}%`;
export const eur = (v: number, digits = 0) => `€${nf(digits).format(v)}`;
export const ms = (v: number) => `${nf(1).format(v)} ms`;

/** Signed values use a true minus sign so columns line up and screen readers say "minus". */
const signed = (s: string, v: number) => (v > 0 ? `+${s}` : v < 0 ? `−${s.replace("-", "")}` : s);
export const lift = (v: number, digits = 1) => signed(`${nf(digits).format(100 * Math.abs(v))}%`, v);
export const pp = (v: number, digits = 2) => signed(`${nf(digits).format(100 * Math.abs(v))} pp`, v);
export const eurDelta = (v: number, digits = 1) => signed(`€${nf(digits).format(Math.abs(v))}`, v);
