import argparse
from pathlib import Path

import qrcode


def main():
    parser = argparse.ArgumentParser(description="Gera QR Code de acesso ao sistema.")
    parser.add_argument("--url", required=True, help="URL que sera aberta ao ler o QR Code.")
    parser.add_argument("--output", default="static/qrcode-garagem.png", help="Arquivo PNG de saida.")
    parser.add_argument("--html", default="static/qrcode.html", help="Pagina HTML simples para impressao.")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    img = qrcode.make(args.url)
    img.save(output)

    html = Path(args.html)
    html.parent.mkdir(parents=True, exist_ok=True)
    image_src = output.name if html.parent == output.parent else output.as_posix()
    html.write_text(
        f"""<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>QR Code - Garagem</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; text-align: center; }}
    img {{ width: min(70vw, 360px); height: auto; image-rendering: pixelated; }}
    .url {{ margin-top: 18px; font-size: 18px; word-break: break-all; }}
    @media print {{ button {{ display: none; }} }}
  </style>
</head>
<body>
  <h1>Acesso Garagem</h1>
  <img src="{image_src}" alt="QR Code do sistema">
  <div class="url">{args.url}</div>
  <p><button onclick="window.print()">Imprimir</button></p>
</body>
</html>
""",
        encoding="utf-8",
    )

    print(f"QR Code gerado: {output}")
    print(f"Pagina para impressao: {html}")
    print(f"URL: {args.url}")


if __name__ == "__main__":
    main()
