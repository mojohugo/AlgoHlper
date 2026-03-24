"use client";

import dynamic from "next/dynamic";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => <div className="editorLoading">正在加载编辑器…</div>,
});

type CodeEditorProps = {
  value: string;
  language: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  height?: number;
  theme?: "light" | "dark";
};

export function CodeEditor({
  value,
  language,
  onChange,
  readOnly = false,
  height = 420,
  theme = "dark",
}: CodeEditorProps) {
  return (
    <div className="editorSurface" style={{ height }}>
      <MonacoEditor
        language={language}
        theme={theme === "light" ? "vs-light" : "vs-dark"}
        value={value}
        onChange={(nextValue) => onChange?.(nextValue ?? "")}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 14,
          lineNumbersMinChars: 3,
          scrollBeyondLastLine: false,
          wordWrap: "on",
          tabSize: 2,
          automaticLayout: true,
          padding: { top: 14, bottom: 14 },
          renderWhitespace: "selection",
          smoothScrolling: true,
          cursorBlinking: "smooth",
          overviewRulerBorder: false,
        }}
      />
    </div>
  );
}
