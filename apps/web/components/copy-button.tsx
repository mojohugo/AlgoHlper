"use client";

import { useEffect, useState } from "react";

type CopyButtonProps = {
  text: string;
  label?: string;
  successLabel?: string;
  className?: string;
};

export function CopyButton({
  text,
  label = "复制",
  successLabel = "已复制",
  className = "button secondary buttonSmall",
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) {
      return;
    }
    const timer = window.setTimeout(() => setCopied(false), 1200);
    return () => window.clearTimeout(timer);
  }, [copied]);

  async function handleCopy() {
    if (!text) {
      return;
    }
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      return;
    }

    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
    setCopied(true);
  }

  return (
    <button type="button" className={className} onClick={() => void handleCopy()} disabled={!text}>
      {copied ? successLabel : label}
    </button>
  );
}
