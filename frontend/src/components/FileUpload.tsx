import {
  type ChangeEvent,
  type DragEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

interface FileUploadProps {
  file: File | null;
  onFile: (file: File) => void;
  onClear: () => void;
}
/** Drag-drop + preview do PDF selecionado. O Confirmar/Cancelar vive no modal. */
export function FileUpload({ file, onFile, onClear }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleFile = useCallback(
    (f: File) => {
      if (f.type === "application/pdf" || /\.pdf$/i.test(f.name)) onFile(f);
    },
    [onFile]
  );

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile]
  );

  if (file) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100">
              <svg className="h-5 w-5 text-emerald-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-medium text-emerald-900">{file.name}</p>
              <p className="text-xs text-emerald-600">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
          </div>
          <button
            onClick={onClear}
            className="cursor-pointer rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-sm font-medium text-neutral-700 transition-colors hover:bg-neutral-50"
          >
            Trocar
          </button>
        </div>
        {previewUrl && (
          <iframe
            title="preview"
            src={previewUrl}
            className="h-[62vh] w-full rounded-xl border border-neutral-200 bg-white"
          />
        )}
      </div>
    );
  }

  return (
    <div
      onDrop={onDrop}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        setIsDragging(false);
      }}
      onClick={() => inputRef.current?.click()}
      className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-all ${
        isDragging
          ? "border-neutral-900 bg-neutral-50"
          : "border-neutral-300 hover:border-neutral-400 hover:bg-neutral-50/50"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        onChange={(e: ChangeEvent<HTMLInputElement>) => {
          const f = e.target.files?.[0];
          if (f) handleFile(f);
        }}
        className="hidden"
      />
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-neutral-100">
        <svg className="h-6 w-6 text-neutral-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
      </div>
      <p className="text-sm font-medium text-neutral-700">
        Arraste o documento (PDF) aqui ou{" "}
        <span className="text-neutral-900 underline underline-offset-2">clique para buscar</span>
      </p>
      <p className="mt-2 text-xs text-neutral-400">Um documento pode conter vários invoices.</p>
    </div>
  );
}
