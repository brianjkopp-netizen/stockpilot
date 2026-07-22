import { describe, it, expect } from "vitest";
import { fmt$, fmtN, fmtPct, fmtBigN, fmtTimestamp } from "../format.js";

describe("fmt$", () => {
  it("renders an em-dash for null", () => {
    expect(fmt$(null)).toBe("—");
  });

  it("renders zero as a dollar amount, not an em-dash", () => {
    expect(fmt$(0)).toBe("$0.00");
  });
});

describe("fmtN", () => {
  it("renders an em-dash for null", () => {
    expect(fmtN(null)).toBe("—");
  });

  it("renders zero", () => {
    expect(fmtN(0)).toBe("0");
  });
});

describe("fmtPct", () => {
  it("renders an em-dash for null", () => {
    expect(fmtPct(null)).toBe("—");
  });

  it("renders zero with a leading plus sign", () => {
    expect(fmtPct(0)).toBe("+0.00%");
  });
});

describe("fmtBigN", () => {
  it("renders an em-dash for null", () => {
    expect(fmtBigN(null)).toBe("—");
  });

  it("renders zero as a plain string", () => {
    expect(fmtBigN(0)).toBe("0");
  });
});

describe("fmtTimestamp", () => {
  it("renders an em-dash for null", () => {
    expect(fmtTimestamp(null)).toBe("—");
  });

  it("renders an em-dash for an empty string", () => {
    expect(fmtTimestamp("")).toBe("—");
  });
});
