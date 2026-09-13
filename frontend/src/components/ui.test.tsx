import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ErrorState } from "@/components/ErrorState";
import { LoadingSpinner } from "@/components/LoadingSpinner";



afterEach(() => {
  cleanup();
});

describe("LoadingSpinner", () => {
  it("renders default and custom labels with status role", () => {
    const { rerender } = render(<LoadingSpinner />);
    expect(screen.getByRole("status")).toHaveTextContent("Загрузка");

    rerender(<LoadingSpinner label="Загружаем цели" />);
    expect(screen.getByRole("status")).toHaveTextContent("Загружаем цели");
  });
});

describe("ErrorState", () => {
  it("shows message and calls onRetry", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Не удалось загрузить данные" onRetry={onRetry} />);

    expect(screen.getByText("Не удалось загрузить данные")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
