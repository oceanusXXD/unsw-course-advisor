// eslint.config.ts
import globals from "globals";
import pluginJs from "@eslint/js";
import tseslint from "typescript-eslint";
import pluginReact from "eslint-plugin-react";
import pluginReactHooks from "eslint-plugin-react-hooks";
import configPrettier from "eslint-config-prettier";

export default tseslint.config(
  pluginJs.configs.recommended, // ESLint 官方推荐的核心规则
  ...tseslint.configs.recommended, // TypeScript 官方推荐的规则集

  {
    // 指定此配置块应用于哪些文件
    files: ["**/*.{js,mjs,cjs,jsx,mjsx,ts,tsx}"],

    // 插件定义
    plugins: {
      react: pluginReact,
      "react-hooks": pluginReactHooks,
    },

    // 语言选项
    languageOptions: {
      parserOptions: {
        ecmaFeatures: { jsx: true }, // 启用对 JSX 的解析
      },
      globals: {
        ...globals.browser, // 包含所有浏览器全局变量，如 `window` 和 `document`
      },
    },

    // React 版本设置
    settings: {
      react: {
        version: "detect", // 自动检测项目中安装的 React 版本
      },
    },

    // 具体的规则集和自定义规则
    rules: {
      // 继承 React 和 React Hooks 的推荐规则
      ...pluginReact.configs.recommended.rules,
      ...pluginReactHooks.configs.recommended.rules,

      "react/prop-types": "off",

      "react/react-in-jsx-scope": "off",
    },
  },

  configPrettier,
);
