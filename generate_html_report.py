"""Generate standalone HTML and printable report from SIEIS_Comprehensive_Project_Report.md."""

from __future__ import annotations

import markdown


def main():
    with open("SIEIS_Comprehensive_Project_Report.md", "r", encoding="utf-8") as f:
        md_content = f.read()

    # Convert markdown to HTML with tables, code fences, etc.
    html_body = markdown.markdown(md_content, extensions=["tables", "fenced_code", "toc"])

    # Mermaid block replacement for markdown ```mermaid fences
    html_body = html_body.replace('<code class="language-mermaid">', '<div class="mermaid">')
    html_body = html_body.replace("</code></pre>", "</div>")
    html_body = html_body.replace('<pre><div class="mermaid">', '<div class="mermaid">')

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SIEIS — Comprehensive Technical Project Report</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

    <!-- KaTeX for LaTeX Math rendering -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>

    <!-- Mermaid for diagrams -->
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>

    <style>
        :root {{
            --font-main: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }}
        body {{
            font-family: var(--font-main);
            line-height: 1.65;
            color: #1e293b;
            background: #f8fafc;
            margin: 0;
            padding: 40px 20px;
        }}
        .report-container {{
            max-width: 960px;
            margin: 0 auto;
            background: #ffffff;
            padding: 50px 60px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
            border: 1px solid #e2e8f0;
        }}
        .top-action-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .btn-print {{
            background: #0284c7;
            color: #ffffff;
            border: none;
            padding: 10px 18px;
            font-size: 0.9rem;
            font-weight: 600;
            border-radius: 6px;
            cursor: pointer;
            box-shadow: 0 2px 4px rgba(2, 132, 199, 0.3);
            transition: background 0.15s ease;
        }}
        .btn-print:hover {{
            background: #0369a1;
        }}
        h1 {{
            font-size: 2.1rem;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 6px;
            letter-spacing: -0.5px;
        }}
        h2 {{
            font-size: 1.45rem;
            font-weight: 700;
            color: #1e293b;
            margin-top: 36px;
            margin-bottom: 14px;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 8px;
        }}
        h3 {{
            font-size: 1.15rem;
            font-weight: 600;
            color: #334155;
            margin-top: 24px;
            margin-bottom: 10px;
        }}
        p, li {{
            font-size: 0.98rem;
            color: #334155;
            margin-bottom: 12px;
        }}
        ul, ol {{
            padding-left: 24px;
            margin-bottom: 16px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 0.88rem;
        }}
        th, td {{
            padding: 10px 12px;
            text-align: left;
            border: 1px solid #cbd5e1;
        }}
        th {{
            background: #f1f5f9;
            font-weight: 600;
            color: #0f172a;
        }}
        tr:nth-child(even) {{
            background: #f8fafc;
        }}
        pre {{
            background: #0f172a;
            color: #f8fafc;
            padding: 16px 20px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: var(--font-mono);
            font-size: 0.85rem;
            line-height: 1.5;
            margin: 18px 0;
        }}
        code {{
            font-family: var(--font-mono);
            background: #e2e8f0;
            color: #0f172a;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.88rem;
        }}
        pre code {{
            background: transparent;
            color: inherit;
            padding: 0;
        }}
        blockquote {{
            border-left: 4px solid #0284c7;
            background: #f0f9ff;
            margin: 18px 0;
            padding: 12px 18px;
            border-radius: 0 8px 8px 0;
            color: #0369a1;
        }}
        .mermaid {{
            margin: 20px 0;
            text-align: center;
        }}
        @media print {{
            body {{
                background: #ffffff;
                padding: 0;
            }}
            .report-container {{
                border: none;
                box-shadow: none;
                padding: 0;
                max-width: 100%;
            }}
            .top-action-bar {{
                display: none;
            }}
            h2 {{
                page-break-before: auto;
            }}
            table, pre {{
                page-break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="top-action-bar">
            <div>
                <strong>Smart Indoor Environmental Intelligence System</strong> — Academic Engineering Report
            </div>
            <button class="btn-print" onclick="window.print()">🖨️ Print / Save as PDF</button>
        </div>
        {html_body}
    </div>

    <script>
        document.addEventListener("DOMContentLoaded", function() {{
            mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});
            renderMathInElement(document.body, {{
                delimiters: [
                    {{left: '$$', right: '$$', display: true}},
                    {{left: '$', right: '$', display: false}},
                    {{left: '\\\\(', right: '\\\\)', display: false}},
                    {{left: '\\\\[', right: '\\\\]', display: true}}
                ],
                throwOnError: false
            }});
        }});
    </script>
</body>
</html>
"""

    with open("SIEIS_Comprehensive_Project_Report.html", "w", encoding="utf-8") as out:
        out.write(full_html)

    print("Generated SIEIS_Comprehensive_Project_Report.html successfully.")


if __name__ == "__main__":
    main()
