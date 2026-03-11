const BASE_URL = "/api/privacy";

/**
 * Triggers a PII export and downloads the resulting ZIP file.
 */
export async function exportUserData(): Promise<void> {
  const response = await fetch(`${BASE_URL}/export`, {
    method: "GET",
    credentials: "include",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: "Export failed" }));
    throw new Error(error.error || "Failed to export user data");
  }

  const blob = await response.blob();
  const contentDisposition = response.headers.get("Content-Disposition") || "";
  const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
  const filename = filenameMatch ? filenameMatch[1] : "pii_export.zip";

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Permanently deletes the current user's account.
 * Requires the confirmation phrase "DELETE_MY_ACCOUNT".
 */
export async function deleteAccount(confirm: string): Promise<{ message: string }> {
  const response = await fetch(`${BASE_URL}/delete`, {
    method: "DELETE",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm }),
  });

  const data = await response.json().catch(() => ({ error: "Unknown error" }));

  if (!response.ok) {
    throw new Error(data.error || "Failed to delete account");
  }

  return data as { message: string };
}
