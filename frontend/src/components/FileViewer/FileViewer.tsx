import { getFileDecryptKey, decryptLicensedFile } from '../../services/api';

async function handleOpenEncryptedFile(encryptedFileJson: any, licenseKey: string, userKeyB64: string) {
  try {
    // 直接使用 decryptLicensedFile 完成完整流程
    const decrypted = await decryptLicensedFile(encryptedFileJson, licenseKey, userKeyB64);
    // 将 decrypted 渲染到 UI
  } catch (err) {
    console.error('解密失败', err);
  }
}
