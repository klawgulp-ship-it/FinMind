import apiClient from "./client";

export async function exportUserData(): Promise<Blob> {
  const response = await apiClient.get<Blob>("/privacy/export", {
    responseType: "blob",
  });
  return response.data;
}

export async function deleteUserData(): Promise<{ detail: string }> {
  const response = await apiClient.delete<{ detail: string }>("/privacy/delete");
  return response.data;
}
