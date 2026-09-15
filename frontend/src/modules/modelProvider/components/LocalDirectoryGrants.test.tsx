import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LocalDirectoryGrants from "./LocalDirectoryGrants";
import { createLocalDirectoryGrant, deleteLocalDirectoryGrant, listLocalDirectoryGrants } from "../api/localDirectoryGrants";

vi.mock("../api/localDirectoryGrants", () => ({
  createLocalDirectoryGrant: vi.fn(), deleteLocalDirectoryGrant: vi.fn(), listLocalDirectoryGrants: vi.fn(),
}));
vi.mock("../utils/cloudDocumentOnboarding", () => ({ markCloudDocumentConnectionSuccess: vi.fn() }));
vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
const key = (name: string) => `modelProvider.cloudDocuments.${name}`;
const grant = { id: "local-grant:1", path: "/Users/me/docs", file_extensions: ["txt"], created_at: "2026-09-14" };

beforeEach(() => { vi.resetAllMocks(); vi.mocked(listLocalDirectoryGrants).mockResolvedValue([]); });

describe("independent directory reading", () => {
  it("adds and revokes a read-only directory without a knowledge base", async () => {
    vi.mocked(createLocalDirectoryGrant).mockResolvedValue(grant);
    vi.mocked(deleteLocalDirectoryGrant).mockResolvedValue(undefined);
    render(<LocalDirectoryGrants canManage />);
    await waitFor(() => expect(screen.getByRole("button", { name: key("localReadAdd") })).toBeEnabled());
    fireEvent.change(screen.getByLabelText(key("localReadPath")), { target: { value: grant.path } });
    fireEvent.click(screen.getByRole("button", { name: key("localReadAdd") }));
    await screen.findByText(grant.path);
    expect(createLocalDirectoryGrant).toHaveBeenCalledWith(grant.path, ["txt", "md", "pdf", "docx", "xlsx", "csv"]);
    fireEvent.click(screen.getByRole("button", { name: key("localReadRemove") }));
    await waitFor(() => expect(screen.queryByText(grant.path)).not.toBeInTheDocument());
    expect(deleteLocalDirectoryGrant).toHaveBeenCalledWith(grant.id);
  });

  it("shows grants without mutation controls for non-admin users", async () => {
    vi.mocked(listLocalDirectoryGrants).mockResolvedValue([grant]);
    render(<LocalDirectoryGrants canManage={false} />);
    await screen.findByText(grant.path);
    expect(screen.queryByRole("button", { name: key("localReadAdd") })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: key("localReadRemove") })).not.toBeInTheDocument();
  });

  it("retains the directory when revocation fails", async () => {
    vi.mocked(listLocalDirectoryGrants).mockResolvedValue([grant]);
    vi.mocked(deleteLocalDirectoryGrant).mockRejectedValue(new Error("unavailable"));
    render(<LocalDirectoryGrants canManage />);
    await screen.findByText(grant.path);
    fireEvent.click(screen.getByRole("button", { name: key("localReadRemove") }));
    await waitFor(() => expect(deleteLocalDirectoryGrant).toHaveBeenCalled());
    expect(screen.getByText(grant.path)).toBeInTheDocument();
  });
});
