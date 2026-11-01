import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SignInButton } from "./SignInButton";

describe("SignInButton", () => {
  it("renders nothing in a build without accounts, as the site is today", () => {
    expect(renderToStaticMarkup(<SignInButton />)).toBe("");
  });
});
