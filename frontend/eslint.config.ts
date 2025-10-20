// eslint.config.ts
import globals from "globals";
import pluginJs from "@eslint/js";
import tseslint from "typescript-eslint";
import pluginReact from "eslint-plugin-react";
import pluginReactHooks from "eslint-plugin-react-hooks";
import configPrettier from "eslint-config-prettier";

/**
 * 这是 ESLint 的现代化 "Flat Config" 配置文件。
 * 它导出一个配置数组，ESLint 会按顺序应用这些配置。
 */
export default tseslint.config(
  // 1. 全局推荐规则和 TypeScript 基础规则
  // ----------------------------------------------------
  pluginJs.configs.recommended, // ESLint 官方推荐的核心规则
  ...tseslint.configs.recommended, // TypeScript 官方推荐的规则集

  // 2. React 相关的特定规则配置
  // ----------------------------------------------------
  {
    // 指定此配置块应用于哪些文件
    files: ["**/*.{js,mjs,cjs,jsx,mjsx,ts,tsx}"],

    // 插件定义
    plugins: {
      "react": pluginReact,
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
      
      // 自定义规则覆盖：
      // 由于我们使用 TypeScript，不需要 React 的 prop-types 验证
      "react/prop-types": "off",
      
      // 从 React 17 开始，不再需要在每个文件中导入 React
      "react/react-in-jsx-scope": "off",
    },
  },

  // 3. Prettier 配置，用于关闭与代码格式化冲突的规则
  // ----------------------------------------------------
  // **重要提示：这个必须是配置数组的最后一项！**
  // 它会关闭所有可能与 Prettier 冲突的 ESLint 规则，确保 Prettier 负责所有代码格式化工作。
  configPrettier
);