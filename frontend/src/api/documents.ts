import { api, apiBase } from "./client";
import type {
  DocumentDetail,
  DocumentListItem,
  DocumentUpdate,
  Metrics,
} from "../types/document";

export const listDocuments = () => api<DocumentListItem[]>("/documents");

export const getDocument = (id: string) => api<DocumentDetail>(`/documents/${id}`);

export const getMetrics = () => api<Metrics>("/dashboard/metrics");

export const updateDocument = (id: string, body: DocumentUpdate) =>
  api<DocumentDetail>(`/documents/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

export const approveDocument = (id: string) =>
  api<{ id: string; status: string }>(`/documents/${id}/approve`, { method: "POST" });

export const rejectDocument = (id: string) =>
  api<{ id: string; status: string }>(`/documents/${id}/reject`, { method: "POST" });

export function uploadDocument(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  return api<{ id: string; status: string }>("/documents/upload", {
    method: "POST",
    body: fd,
  });
}

export const fileUrl = (id: string) => `${apiBase()}/documents/${id}/file`;
