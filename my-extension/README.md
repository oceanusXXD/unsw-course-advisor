# API Runner (Local) - 插件说明

## 目录结构

见你所给出的结构。

## 快速开始（测试）

1. 在本地创建文件夹 `my-extension/`，将本示例所有文件放入。
2. 浏览器打开 `chrome://extensions/`，开启“开发者模式”。
3. 点击“加载已解压的扩展程序”，选择 `my-extension/` 文件夹。
4. 安装后，你会在工具栏看到扩展图标。打开目标站点（例如 `https://myplan.unsw.edu.au/`），点击扩展打开 popup。

## 测试解密（本地占位）

- 样例加密包文件在 `templates/encrypted_template.json`（默认使用 `cipher: "PLAIN"` 用于调试，本地会直接返回明文）。
- 在 popup 点击“上传/粘贴 加密包”，将 `templates/encrypted_template.json` 的内容粘贴进去，然后点击“解密并保存”。
- 解密成功后，popup 会显示解密得到的参数，选择 API 并点击“在当前标签页触发请求”可在页面上下文发起请求（带用户登录态）。

## 支持的解密占位（插件端）

- `PLAIN`：直接包含 `plaintext` 字段（仅用于本地调试）。
- `PLAINBASE64`：`ciphertext` 为 base64(plaintext)。
- `AES-GCM` + `PBKDF2`：示例实现，需后端按相同参数加密才能解密（见 `crypto.js`）。

## 注意

- 真实场景下请让后端使用与插件约定一致的加密格式（算法、KDF、salt、iv、编码等）。
