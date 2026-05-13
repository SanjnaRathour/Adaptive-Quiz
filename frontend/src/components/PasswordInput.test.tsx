import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PasswordInput } from "./PasswordInput";

describe("PasswordInput", () => {
  it("renders as password type by default", () => {
    const { container } = render(
      <PasswordInput value="secret" onChange={() => {}} label="Password" />,
    );
    expect(container.querySelector("input")).toHaveAttribute("type", "password");
  });

  it("reveals password when eye button is clicked", async () => {
    const user = userEvent.setup();
    const { container } = render(<PasswordInput value="secret" onChange={() => {}} />);
    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(container.querySelector("input")).toHaveAttribute("type", "text");
  });

  it("hides password again on second click", async () => {
    const user = userEvent.setup();
    const { container } = render(<PasswordInput value="secret" onChange={() => {}} />);
    const btn = screen.getByRole("button");
    await user.click(btn);
    await user.click(btn);
    expect(container.querySelector("input")).toHaveAttribute("type", "password");
  });

  it("sets aria-pressed to reflect visibility state", async () => {
    const user = userEvent.setup();
    render(<PasswordInput value="" onChange={() => {}} />);
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-pressed", "false");
    await user.click(btn);
    expect(btn).toHaveAttribute("aria-pressed", "true");
  });

  it("shows label when provided", () => {
    render(<PasswordInput value="" onChange={() => {}} label="Enter password" />);
    expect(screen.getByText("Enter password")).toBeInTheDocument();
  });

  it("shows hint text when provided", () => {
    render(
      <PasswordInput value="" onChange={() => {}} hint="Must be at least 8 characters" />,
    );
    expect(screen.getByText("Must be at least 8 characters")).toBeInTheDocument();
  });
});
