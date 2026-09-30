if (window.mermaid) {
  mermaid.initialize({ startOnLoad: false });
  mermaid.run();
} else {
  console.error("mermaid-init.js: window.mermaid is not defined -- mermaid.min.js did not load");
}
