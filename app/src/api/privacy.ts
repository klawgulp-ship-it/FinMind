import axios from "axios";

const BASE_URL = "/api/privacy";

/**
 * Download the authenticated user's PII export as a ZIP file.
 * Triggers a browser file download.
 */
export async function exportUserData(): Promise<void> {
  const response = await axios.get(`${BASE_URL}/export`, {
    responseType: "blob",
    withCredentials: true,
  });

  const contentDisposition: string =
    response.headers["content-disposition"] ?? "";
  const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
  const filename = filenameMatch ? filenameMatch[1] : "user_data_export.zip";

  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/**
 * Permanently delete the authenticated user's account and all associated data.
 * The caller must supply the exact confirmation phrase: 'DELETE MY ACCOUNT'.
 */
export async function deleteAccount(
  confirmationPhrase: string
): Promise<{ message: string }> {
  const response = await axios.delete<{ message: string }>(`${BASE_URL}/delete`, {
    data: { confirm: confirmationPhrase },
    withCredentials: true,
  });
  return response.data;
}
