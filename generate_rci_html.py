"""Generate standalone HTML and printable report from SIEIS_Room_Comfort_Index_Specification.md."""

from __future__ import annotations

import markdown


def main():
    with open("SIEIS_Room_Comfort_Index_Specification.md", "r", encoding="utf-8") as f:
        md_content = f.read()

    # Convert markdown to HTML with tables, code fences, etc.
    html_body = markdown.markdown(md_content, extensions=["tables", "fenced_code", "toc"])

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SIEIS — Room Comfort Index (RCI) Authoritative Specification</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

    <!-- KaTeX for LaTeX Math rendering -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>

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
        .nav-links {{
            display: flex;
            gap: 12px;
        }}
        .nav-link {{
            color: #0284c7;
            text-decoration: none;
            font-size: 0.88rem;
            font-weight: 500;
        }}
        .nav-link:hover {{
            text-decoration: underline;
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
            font-size: 0.95rem;
            color: #334155;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 0.88rem;
        }}
        th, td {{
            padding: 10px 12px;
            border: 1px solid #cbd5e1;
            text-align: left;
        }}
        th {{
            background: #f1f5f9;
            font-weight: 600;
            color: #0f172a;
        }}
        tr:nth-child(even) {{
            background: #f8fafc;
        }}
        code {{
            font-family: var(--font-mono);
            font-size: 0.85em;
            background: #f1f5f9;
            padding: 2px 6px;
            border-radius: 4px;
            color: #0f172a;
            border: 1px solid #e2e8f0;
        }}
        pre {{
            background: #0f172a;
            color: #f8fafc;
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: var(--font-mono);
            font-size: 0.85rem;
            line-height: 1.5;
        }}
        pre code {{
            background: transparent;
            color: inherit;
            padding: 0;
            border: none;
        }}
        blockquote {{
            border-left: 4px solid #0284c7;
            background: #f0f9ff;
            margin: 20px 0;
            padding: 12px 20px;
            color: #0369a1;
            border-radius: 0 8px 8px 0;
        }}
        blockquote p {{
            margin: 0;
            color: inherit;
        }}
        .katex-display {{
            margin: 1.2em 0;
            overflow-x: auto;
            overflow-y: hidden;
            padding: 8px 0;
        }}
        @media print {{
            body {{
                background: #ffffff;
                padding: 0;
            }}
            .report-container {{
                box-shadow: none;
                border: none;
                padding: 0;
                max-width: 100%;
            }}
            .top-action-bar {{
                display: none;
            }}
            pre, blockquote, table {{
                page-break-inside: avoid;
            }}
            h2, h3 {{
                page-break-after: avoid;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="top-action-bar">
            <div class="nav-links">
                <a href="/" class="nav-link">&larr; Back to Dashboard</a>
                <a href="/report" class="nav-link">Comprehensive Report</a>
            </div>
            <button class="btn-print" onclick="window.print()">🖨️ Print / Save as PDF</button>
        </div>

        {html_body}
    </div>

    <script>
        document.addEventListener("DOMContentLoaded", function() {{
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

    with open("SIEIS_Room_Comfort_Index_Specification.html", "w", encoding="utf-8") as f:
        f.write(full_html)

    print("Successfully generated SIEIS_Room_Comfort_Index_Specification.html")


if __name__ == "__main__":
    main()
