import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { uploadDocument } from "../api/documents";
import { FileUpload } from "./FileUpload";

export function NewDocumentModal({ onClose }: { onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (f: File) => uploadDocument(f),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
      onClose();
    },
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-neutral-900">Novo documento</h2>
          <button
            onClick={onClose}
            className="cursor-pointer rounded-lg p-1 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-600"
            aria-label="Fechar"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <FileUpload file={file} onFile={setFile} onClear={() => setFile(null)} />

        {mutation.isError && (
          <p className="mt-3 text-sm text-red-600">
            Falha no upload: {(mutation.error as Error).message}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="cursor-pointer rounded-lg border border-neutral-200 bg-white px-4 py-2 text-sm font-medium text-neutral-700 transition-colors hover:bg-neutral-50"
          >
            Cancelar
          </button>
          <button
            disabled={!file || mutation.isPending}
            onClick={() => file && mutation.mutate(file)}
            className="cursor-pointer rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {mutation.isPending ? "Enviando…" : "Enviar"}
          </button>
        </div>
      </div>
    </div>
  );
}
