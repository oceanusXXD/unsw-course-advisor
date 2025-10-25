import { useState, useCallback, useRef } from "react";
import { UploadedFile, UploadError } from "../types/upload";

interface UseFileUploadOptions {
  maxFiles?: number;
  maxSize?: number; // bytes
  acceptedTypes?: string[];
  onFilesSelected?: (files: UploadedFile[]) => void;
}

export const useFileUpload = (options: UseFileUploadOptions = {}) => {
  const {
    maxFiles = 5,
    maxSize = 10 * 1024 * 1024, // 10MB
    acceptedTypes = ["image/*", "application/pdf", ".txt", ".doc", ".docx"],
    onFilesSelected,
  } = options;

  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [errors, setErrors] = useState<UploadError[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = useCallback(
    (file: File): string | null => {
      // 检查文件大小
      if (file.size > maxSize) {
        return `File size exceeds ${(maxSize / (1024 * 1024)).toFixed(0)}MB limit`;
      }

      // 检查文件类型
      const fileType = file.type;
      const fileName = file.name.toLowerCase();

      const isAccepted = acceptedTypes.some((type) => {
        if (type.startsWith(".")) {
          return fileName.endsWith(type);
        }
        if (type.endsWith("/*")) {
          const category = type.split("/")[0];
          return fileType.startsWith(category);
        }
        return fileType === type;
      });

      if (!isAccepted) {
        return "File type not supported";
      }

      return null;
    },
    [maxSize, acceptedTypes],
  );

  const createFilePreview = useCallback(
    (file: File): Promise<string | undefined> => {
      return new Promise((resolve) => {
        if (!file.type.startsWith("image/")) {
          resolve(undefined);
          return;
        }

        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target?.result as string);
        reader.onerror = () => resolve(undefined);
        reader.readAsDataURL(file);
      });
    },
    [],
  );

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;

      const newErrors: UploadError[] = [];
      const validFiles: UploadedFile[] = [];

      // 检查文件数量限制
      if (uploadedFiles.length + files.length > maxFiles) {
        newErrors.push({
          file: "general",
          message: `Cannot upload more than ${maxFiles} files`,
        });
        setErrors(newErrors);
        return;
      }

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const error = validateFile(file);

        if (error) {
          newErrors.push({ file: file.name, message: error });
        } else {
          const preview = await createFilePreview(file);
          validFiles.push({
            id: `${Date.now()}_${i}_${Math.random().toString(36).substr(2, 9)}`,
            file,
            name: file.name,
            size: file.size,
            type: file.type,
            preview,
            uploadedAt: new Date(),
          });
        }
      }

      if (validFiles.length > 0) {
        const updatedFiles = [...uploadedFiles, ...validFiles];
        setUploadedFiles(updatedFiles);
        onFilesSelected?.(updatedFiles);
      }

      setErrors(newErrors);
    },
    [uploadedFiles, maxFiles, validateFile, createFilePreview, onFilesSelected],
  );

  const removeFile = useCallback(
    (fileId: string) => {
      setUploadedFiles((prev) => {
        const updated = prev.filter((f) => f.id !== fileId);
        onFilesSelected?.(updated);
        return updated;
      });
    },
    [onFilesSelected],
  );

  const clearFiles = useCallback(() => {
    setUploadedFiles([]);
    setErrors([]);
    onFilesSelected?.([]);
  }, [onFilesSelected]);

  const openFilePicker = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  return {
    uploadedFiles,
    errors,
    fileInputRef,
    handleFiles,
    removeFile,
    clearFiles,
    openFilePicker,
  };
};
