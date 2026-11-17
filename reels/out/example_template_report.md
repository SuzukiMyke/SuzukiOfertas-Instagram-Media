# Relatório do reel `example_template`

- Resultado técnico automático: **✔ sem erros bloqueantes**
- Estado: implementado e testado localmente. NÃO validado com serviço real; NÃO aprovado para produção.
- Arquivo: `reels/out/example_template.mp4`
- SHA-256: `26147ec1945f979960aa3c946c77a2d6d3d4b4b1e3a3b643ba1a2726c4f9454f`
- MD5 dos quadros decodificados (framemd5): `3016e6c7a522938b51965ff02d1c944c`
- Duração: 18.133 s · Tamanho: 4.01 MB
- Render: 35.86 s · pico de memória do FFmpeg: 490.8 MB

## Ferramentas

- python: 3.13.18
- pillow: 12.3.0
- ffmpeg: ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers
- ffprobe: ffprobe version 6.1.1-3ubuntu5 Copyright (c) 2007-2023 the FFmpeg developers
- libx264: True
- aac: True
- platform: Linux-6.18.44-fc-v553-x86_64-with-glibc2.39

## Linha do tempo

| Segmento | Início (s) | Fim (s) | Duração (s) | Transição de entrada |
|---|---|---|---|---|
| hook (hook) | 0.000 | 2.800 | 2.800 | — |
| e1 (scene) | 2.300 | 6.700 | 4.400 | circleopen 0.50 s |
| e2 (scene) | 6.233 | 10.633 | 4.400 | slideup 0.47 s |
| e3 (scene) | 10.233 | 14.633 | 4.400 | dissolve 0.40 s |
| cta (cta) | 14.133 | 18.133 | 4.000 | smoothleft 0.50 s |

## Checagens

| Checagem | OK | Detalhe |
|---|---|---|
| gancho ≤ 3.0 s | ✔ | 2.80 s |
| CTA presente e ≥ 2.5 s | ✔ | 4.00 s |
| camadas dentro da margem segura, fontes mínimas, contraste e logo | ✔ | 28 camadas verificadas por geometria |
| contraste mínimo ≥ 4.5 | ✔ | pior caso 6.47:1 |
| regras de conteúdo (seção 4) | ✔ | 0 erro(s) |
| contêiner MP4 | ✔ | mov,mp4,m4a,3gp,3g2,mj2 |
| um fluxo de vídeo | ✔ | 1 fluxo(s) |
| codec h264 | ✔ | h264 |
| pix_fmt yuv420p | ✔ | yuv420p |
| perfil High/Main | ✔ | High |
| resolução 1080x1920 | ✔ | 1080x1920 |
| razão 9:16 | ✔ | 9:16 |
| fps 30 constante | ✔ | r=30/1 avg=30/1 |
| SAR 1:1 | ✔ | 1:1 |
| bitrate de vídeo ≤ 12 Mbps | ✔ | 1.76 Mbps |
| duração 15–20 s | ✔ | 18.133 s |
| duração ≤ 90 s | ✔ | 18.133 s |
| tamanho ≤ 100 MB | ✔ | 4.01 MB |
| moov no início (faststart) | ✔ | True |
| sem faixa de áudio (modo silent) | ✔ | 0 faixa(s) |
| quadro 'inicio' não uniforme | ✔ | desvio-padrão 22.3 |
| quadro 'hook_hook_meio' não uniforme | ✔ | desvio-padrão 54.4 |
| quadro 'scene_e1_meio' não uniforme | ✔ | desvio-padrão 45.0 |
| quadro 'scene_e2_meio' não uniforme | ✔ | desvio-padrão 46.6 |
| quadro 'scene_e3_meio' não uniforme | ✔ | desvio-padrão 49.8 |
| quadro 'cta_cta_meio' não uniforme | ✔ | desvio-padrão 58.8 |
| quadro 'fim' não uniforme | ✔ | desvio-padrão 58.8 |
| logo íntegro (hook) | ✔ | diferença média 8.70 (máx. 14.0) |
| logo íntegro (e1) | ✔ | diferença média 8.87 (máx. 14.0) |
| logo íntegro (e2) | ✔ | diferença média 8.93 (máx. 14.0) |
| logo íntegro (e3) | ✔ | diferença média 8.73 (máx. 14.0) |
| logo íntegro (cta) | ✔ | diferença média 6.90 (máx. 14.0) |
| movimento de câmera presente (e1) | ✔ | diferença média entre quadros 0.568 |
| movimento sem saltos (e1) (aviso) | ✔ | máx/mediana = 1.06 em 11 pares (t=4.40s; limite 3.0) |
| movimento de câmera presente (e2) | ✔ | diferença média entre quadros 0.638 |
| movimento sem saltos (e2) (aviso) | ✔ | máx/mediana = 1.07 em 11 pares (t=7.89s; limite 3.0) |
| movimento de câmera presente (e3) | ✔ | diferença média entre quadros 0.309 |
| movimento sem saltos (e3) (aviso) | ✔ | máx/mediana = 1.35 em 11 pares (t=11.82s; limite 3.0) |

## Origem das imagens

| Cena | Categoria | Arquivo | Tipo | Origem | Licença |
|---|---|---|---|---|---|
| e1 | Esporte e lazer | `reels/assets/synthetic/s4_esporte.jpg` | synthetic_demo | gerado por reel_gen/synth.py (padrão waves, seed 404) | material próprio do projeto (sintético, sem terceiros) |
| e2 | Beleza e cuidados | `reels/assets/synthetic/s5_beleza.jpg` | synthetic_demo | gerado por reel_gen/synth.py (padrão rings, seed 505) | material próprio do projeto (sintético, sem terceiros) |
| e3 | Ferramentas e jardim | `reels/assets/synthetic/s6_ferramentas.jpg` | synthetic_demo | gerado por reel_gen/synth.py (padrão dots, seed 606) | material próprio do projeto (sintético, sem terceiros) |

## Quadros de verificação

- `reels/out/frames/example_template/00_inicio.jpg` — inicio (t=0.00s, desvio-padrão 22.3)
- `reels/out/frames/example_template/01_hook_hook_meio.jpg` — hook_hook_meio (t=1.15s, desvio-padrão 54.4)
- `reels/out/frames/example_template/02_scene_e1_meio.jpg` — scene_e1_meio (t=4.52s, desvio-padrão 45.0)
- `reels/out/frames/example_template/03_scene_e2_meio.jpg` — scene_e2_meio (t=8.47s, desvio-padrão 46.6)
- `reels/out/frames/example_template/04_scene_e3_meio.jpg` — scene_e3_meio (t=12.38s, desvio-padrão 49.8)
- `reels/out/frames/example_template/05_cta_cta_meio.jpg` — cta_cta_meio (t=17.88s, desvio-padrão 58.8)
- `reels/out/frames/example_template/06_fim.jpg` — fim (t=18.03s, desvio-padrão 58.8)
