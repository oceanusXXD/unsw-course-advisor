// src/lib/markdown.jsx
import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSlug from 'rehype-slug';
import rehypeHighlight from 'rehype-highlight';
import rehypeAutolinkHeadings from 'rehype-autolink-headings';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import 'highlight.js/styles/github-dark.css';
import '../styles/markdown.css';

import CodeBlock from '../components/CodeBlock/CodeBlock.jsx';

// 允许代码高亮 & 标题锚点等属性
const schema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    // 允许 code block 的语言类名（language-xxx）
    code: [...(defaultSchema.attributes?.code || []), ['className', /^language-[a-z0-9-]+$/]],
    pre: [...(defaultSchema.attributes?.pre || []), ['className', /^.*$/]],
    span: [
      ...(defaultSchema.attributes?.span || []),
      ['className', /^hljs-.*$/], // 高亮类
    ],
    a: [
      ...(defaultSchema.attributes?.a || []),
      'href',
      'title',
      'target',
      ['rel', /^(noopener|noreferrer|nofollow)(\s+(noopener|noreferrer|nofollow))*$/],
      ['className', /^.*$/],
      ['ariaHidden', /^(true|false)$/],
      ['tabIndex', /^-?\d+$/],
    ],
    h1: [...(defaultSchema.attributes?.h1 || []), 'id'],
    h2: [...(defaultSchema.attributes?.h2 || []), 'id'],
    h3: [...(defaultSchema.attributes?.h3 || []), 'id'],
    h4: [...(defaultSchema.attributes?.h4 || []), 'id'],
    h5: [...(defaultSchema.attributes?.h5 || []), 'id'],
    h6: [...(defaultSchema.attributes?.h6 || []), 'id'],
    input: [
      ...(defaultSchema.attributes?.input || []),
      ['type', 'checkbox'],
      'checked',
      'disabled',
    ],
  },
};

export function SafeMarkdown({ children, className = '' }) {
  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[
          rehypeSlug,
          rehypeHighlight,
          [
            rehypeAutolinkHeadings,
            {
              behavior: 'append',
              properties: { className: ['heading-anchor'], ariaHidden: 'true', tabIndex: -1 },
              content: { type: 'text', value: ' #' },
            },
          ],
          [rehypeSanitize, schema],
        ]}
        components={{
          code({ node, inline, className, children, ...props }) {
            return (
              <CodeBlock node={node} inline={inline} className={className} {...props}>
                {children}
              </CodeBlock>
            );
          },
          a({ children, href, ...props }) {
            const isExternal = href?.startsWith('http');
            return (
              <a
                href={href}
                {...props}
                target={isExternal ? '_blank' : undefined}
                rel={isExternal ? 'noopener noreferrer' : undefined}
              >
                {children}
              </a>
            );
          },
          table({ children, ...props }) {
            return (
              <div className="md-table-wrapper">
                <table {...props}>{children}</table>
              </div>
            );
          },
          img({ src, alt, ...props }) {
            return <img src={src} alt={alt || ''} loading="lazy" {...props} />;
          },
          input({ ...props }) {
            // 任务列表勾选框（只读）
            return <input {...props} disabled readOnly />;
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
