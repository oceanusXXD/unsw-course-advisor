# Accounts API 文档

## 概述

本 API 提供用户认证、许可证管理及文件解密功能。部分接口会调用内部 CryptoService 进行加密/解密操作。

**基础路径：** `/api/accounts/`

**认证方式：** JWT Bearer Token（部分接口允许匿名访问，如注册、登录）

---

## 用户认证接口

### 1. 用户注册

**URL:** `/register/`

**方法:** POST

**权限:** AllowAny

**请求体:**
json
{
"email": "user@example.com",
"username": "username",
"password": "password123"
}

**返回（201 Created）:**
json
{
"message": "注册成功",
"user": {
"email": "user@example.com",
"username": "username"
},
"tokens": {
"access_token": "<JWT_ACCESS_TOKEN>",
"refresh_token": "<JWT_REFRESH_TOKEN>"
}
}

**返回（400 Bad Request）:** 注册失败或参数不完整

---

### 2. 用户登录

**URL:** `/login/`

**方法:** POST

**权限:** AllowAny

**请求体:**
json
{
"email": "user@example.com",
"password": "password123"
}

**返回（200 OK）:**
json
{
"access": "<JWT_ACCESS_TOKEN>",
"refresh": "<JWT_REFRESH_TOKEN>"
}

**返回（401 Unauthorized）:** 认证失败

---

### 3. 获取当前用户信息

**URL:** `/me/`

**方法:** GET

**权限:** IsAuthenticated

**返回（200 OK）:**
json
{
"user": {
"id": 1,
"email": "user@example.com",
"username": "username",
"is_active": true,
"is_staff": false,
"date_joined": "2025-01-01T12:00:00Z",
"last_login": "2025-10-01T12:00:00Z",
"license": {
"license_key": "LIC-XXXXXXXXXXXX",
"device_id": "device123",
"license_active": true,
"license_activated_at": "2025-10-01T12:00:00Z",
"license_expires_at": "2026-10-01T12:00:00Z"
}
}
}

---

### 4. 用户注销

**URL:** `/logout/`

**方法:** POST

**权限:** IsAuthenticated

**请求体:**
json
{
"refresh": "<JWT_REFRESH_TOKEN>"
}

**返回（200 OK）:** 成功注销，refresh token 被拉黑

**返回（400/500）:** 登出失败

---

### 5. 修改密码

**URL:** `/change-password/`

**方法:** POST

**权限:** IsAuthenticated

**请求体:**
json
{
"old_password": "oldpass123",
"new_password": "newpass456"
}

**返回（200 OK）:** 密码修改成功

**返回（400/500）:** 原密码错误或修改失败

---

## 许可证管理接口

### 1. 激活许可证

**URL:** `/license/activate/`

**方法:** POST

**权限:** IsAuthenticated

**请求体:**
json
{
"device_id": "device123"
}

**返回（201 Created）:**
json
{
"license_key": "LIC-XXXXXXXXXXXX",
"user_key": "<BASE64_USER_KEY>",
"device_id": "device123",
"license_active": true,
"license_expires_at": "2026-10-01T12:00:00Z",
"message": "许可证已激活（请妥善保存 user_key）"
}

**返回（500 Internal Server Error）:** 激活失败

> **注意：** user_key 由 CryptoService 派生，请妥善保存

---

### 2. 验证许可证

**URL:** `/license/validate/`

**方法:** POST

**权限:** IsAuthenticated

**请求体:**
json
{
"license_key": "LIC-XXXXXXXXXXXX"
}

**返回（200 OK）:**
json
{
"valid": true,
"is_owner": true,
"owner_user_id": 1,
"owner_email": "user@example.com",
"expired": false,
"license_active": true,
"license_activated_at": "2025-10-01T12:00:00Z",
"license_expires_at": "2026-10-01T12:00:00Z"
}

**返回（400 Bad Request）:** 许可证无效或过期

---

### 3. 获取当前用户许可证信息

**URL:** `/license/my/`

**方法:** GET

**权限:** IsAuthenticated

**返回（200 OK）:**
json
{
"license_key": "LIC-XXXXXXXXXXXX",
"device_id": "device123",
"license_active": true,
"license_activated_at": "2025-10-01T12:00:00Z",
"license_expires_at": "2026-10-01T12:00:00Z"
}

---

### 4. 获取文件解密密钥

**URL:** `/license/file-key/`

**方法:** POST

**权限:** IsAuthenticated

**请求体:**
json
{
"license_key": "LIC-XXXXXXXXXXXX",
"encrypted_file": {
"file_id": "file123"
}
}

**返回（200 OK）:**
json
{
"message": "文件解密密钥已成功生成，并由您的 user_key 加密。",
"wrapped_file_key": {
"nonce": "<BASE64>",
"tag": "<BASE64>",
"ciphertext": "<BASE64>"
}
}

**返回（403/404/500）:** 许可证无效、未激活、过期或文件 ID 不存在

> **注意：** wrapped_file_key 是 CryptoService.encrypt_content_with_key 加密后的结果，客户端需用 user_key 解密

---

## CryptoService 调用说明

> **内部方法，不直接作为 API 接口**

### 1. 派生用户密钥

python
CryptoService.derive_user_key(user_identifier: str) -> bytes

**参数:**

- `user_identifier`：用户唯一标识（通常是 user.id，字符串或数字类型）

**返回值:**

- `bytes`：32 字节的用户密钥

**说明:**

- 使用服务器主密钥和用户唯一标识派生用户密钥
- 在 ActivateLicenseView 中生成 user_key 并返回给前端

---

### 2. 加密文件密钥

python
CryptoService.encrypt_file_key(file_key: bytes) -> Dict[str, str]

**参数:**

- `file_key`：原始文件密钥，32 字节

**返回值:**
json
{
"nonce": "<BASE64>",
"tag": "<BASE64>",
"encrypted_key": "<BASE64>"
}

**说明:**

- 使用服务器主密钥 AES-GCM 加密文件密钥
- 返回的值会存入数据库 FileKey 表中

---

### 3. 解密文件密钥

python
CryptoService.decrypt_file_key(encrypted_key_package: Dict[str, bytes]) -> bytes

**参数:**
python
encrypted_key_package = {
"nonce": bytes,
"tag": bytes,
"encrypted_key": bytes
}

**返回值:**

- `bytes`：解密后的原始文件密钥

**说明:**

- 使用服务器主密钥解密数据库中存储的文件密钥
- 在 GetFileDecryptKeyView 内部调用

---

### 4. 用用户密钥加密文件密钥

python
CryptoService.encrypt_for_user(file_key: bytes, user_key_b64: str) -> Dict[str, str]

**参数:**

- `file_key`：原始文件密钥
- `user_key_b64`：Base64 编码的用户密钥

**返回值:**
json
{
"nonce": "<BASE64>",
"tag": "<BASE64>",
"encrypted_key": "<BASE64>"
}

**说明:**

- 使用用户密钥加密文件密钥，返回给前端
- 前端可用 user_key 解密得到原始文件密钥

---

### 5. 文件内容加解密

#### a. 加密文件内容

python
CryptoService.encrypt_file_content(plaintext: bytes, file_key: bytes) -> Dict[str, str]

**参数:**

- `plaintext`：原始文件内容
- `file_key`：文件密钥

**返回值:**
json
{
"nonce": "<BASE64>",
"tag": "<BASE64>",
"ciphertext": "<BASE64>"
}

**说明:**

- 使用文件密钥 AES-GCM 加密文件内容

#### b. 解密文件内容

python
CryptoService.decrypt_file_content(nonce_b64: str, tag_b64: str, ciphertext_b64: str, file_key: bytes) -> bytes

**参数:**

- `nonce_b64`：Base64 编码的 nonce
- `tag_b64`：Base64 编码的 tag
- `ciphertext_b64`：Base64 编码的密文
- `file_key`：文件密钥

**返回值:**

- `bytes`：解密后的原始文件内容

---

## 许可证辅助函数

### 1. 验证用户许可证

python
verify_license_validity(user) -> Tuple[bool, str]

**参数:**

- `user`：User 对象

**返回值:**

- `(bool, str)` - bool：是否有效，str：错误信息或 "许可证有效"

**说明:**

- 检查 license_active、license_key 是否存在
- 检查是否过期

---

### 2. 获取许可证剩余天数

python
get_license_remaining_days(user) -> Optional[int]

**参数:**

- `user`：User 对象

**返回值:**

- `int`：剩余天数
- `None`：永久有效

**说明:**

- 用于前端显示许可证有效期
