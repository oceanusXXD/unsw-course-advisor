export interface UploadedFile {
  id: string;
  file: File;
  name: string;
  size: number;
  type: string;
  preview?: string; // 图片预览 URL
  uploadedAt: Date;
}

export interface UploadError {
  file: string;
  message: string;
}
