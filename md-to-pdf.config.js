module.exports = {
  pdf_options: {
    format: "A4",
    margin: {
      top: "20mm",
      bottom: "20mm",
      left: "18mm",
      right: "18mm",
    },
    printBackground: true,
  },
  stylesheet_encoding: "utf-8",
  css: `
    body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11pt; line-height: 1.45; color: #222; }
    h1 { border-bottom: 2px solid #ccc; padding-bottom: 4px; }
    h2 { border-bottom: 1px solid #ddd; padding-bottom: 3px; margin-top: 24px; }
    h3 { margin-top: 18px; }
    code { background: #f4f4f4; padding: 1px 4px; border-radius: 3px; font-size: 0.9em; }
    pre { background: #f6f8fa; padding: 10px; border-radius: 4px; overflow-x: auto; font-size: 9pt; }
    pre code { background: transparent; padding: 0; }
    table { border-collapse: collapse; margin: 10px 0; }
    th, td { border: 1px solid #ccc; padding: 5px 9px; text-align: left; }
    th { background: #f0f0f0; }
    img { max-width: 100%; display: block; margin: 10px auto; }
    a { color: #0366d6; }
  `,
};
