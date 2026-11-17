# Gerador de Reels — Suzuki Ofertas (piloto técnico v1)

Gera Reels 1080×1920 / 30 fps / H.264 a partir de uma config JSON.
**Pillow** desenha camadas estáticas (PNG com alfa); **FFmpeg** faz todo o movimento
(zoom/pan com easing, textos que deslizam e esmaecem, transições `xfade`) e a codificação.
Python só orquestra. Sem IA, sem serviços pagos, sem rede.

> Estado: implementado e testado localmente. **Não** validado com serviço real e **não**
> aprovado para produção. Ver `STATUS_REELS.md`.

## Requisitos

Python 3.12+, Pillow, FFmpeg/FFprobe com `libx264` (já presentes no ambiente). Nada a instalar.

## Uso (a partir de `reels/`)

```bash
python3 -m reel_gen check configs/pilot_demo_01.json      # esquema + regras + tempos + camadas (sem FFmpeg)
python3 -m reel_gen build configs/pilot_demo_01.json      # renderiza + valida + relatório
python3 -m reel_gen cta   configs/pilot_demo_01.json      # só o CTA (reaproveitável)
python3 -m reel_gen validate configs/pilot_demo_01.json   # revalida o MP4 existente
python3 -m reel_gen probe out/pilot_demo_01.mp4
python3 -m reel_gen synth                                 # regera os fundos sintéticos
python3 -m unittest discover -s tests -t .                # testes (~2 min, inclui e2e)
```

Saídas em `reels/out/` (fora do Git, exceto o MP4 do piloto e os relatórios):
`<id>.mp4`, `<id>_report.json/.md`, `frames/<id>/*.jpg` (quadros de verificação),
`work/<id>/` (camadas PNG, fundos, intermediários e `plan.json`).

## Como funciona

1. `config.py` mescla `configs/defaults.json` e valida o esquema (`schema/reel.schema.md`).
2. `rules.py` aplica a política de `configs/content_policy.json`.
3. `timeline.py` calcula segmentos (gancho → cenas → CTA), offsets do `xfade` e janelas de texto.
4. `layers.py` diagrama blocos (quebra de linha pela largura real da fonte, painéis, logo) e
   verifica margem segura, tamanhos mínimos, contraste e proporção do logo.
5. `ffmpeg_build.py` gera um comando por segmento (zoompan + overlays) e um passe final (xfade).
6. `validate.py` confere o MP4 (ffprobe, faststart, quadros, logo, movimento) e grava o relatório.

## Política de conteúdo (bloqueante)

- Nada de preço, desconto, estoque ou avaliação sem `verified_at` + `source_url` e foto real.
- Termos proibidos ("menor preço", "imperdível", "últimas unidades", "garantido"…) em qualquer texto.
- Imagem não real sempre com rótulo na tela; nunca como modelo específico de produto.
- Somente arquivos locais (URL remota é erro); `origin` e `license` obrigatórios.
- Somente os canais oficiais registrados; `disclosure` obrigatório no CTA.
- Áudio só no modo `licensed`, com licença documentada e arquivo em `assets/audio_licensed/`.

## Nova config (sem mudar código)

Copie `configs/example_template.json` (modelo comentado), troque categorias, textos, imagens,
tempos, transições e câmera, e rode `build`. O próprio modelo foi renderizado e aprovado sem
nenhuma alteração de código.
