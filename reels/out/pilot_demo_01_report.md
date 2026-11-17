# Relatório do reel `pilot_demo_01`

- Resultado técnico automático: **✔ sem erros bloqueantes**
- Estado: implementado e testado localmente. NÃO validado com serviço real; NÃO aprovado para produção.
- Arquivo: `reels/out/pilot_demo_01.mp4`
- SHA-256: `1aadb48a3f06095cc9a84c98c592a7c129f628dac2245d6ae3533f4d48e2a1df`
- MD5 dos quadros decodificados (framemd5): `93c5c15ca189b3a3b86bbc14449ec7a4`
- Duração: 18.300 s · Tamanho: 3.28 MB
- Render: 34.54 s · pico de memória do FFmpeg: 491.3 MB

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
| hook (hook) | 0.000 | 2.500 | 2.500 | — |
| s1 (scene) | 2.100 | 6.700 | 4.600 | fade 0.40 s |
| s2 (scene) | 6.300 | 10.900 | 4.600 | slideleft 0.40 s |
| s3 (scene) | 10.500 | 15.100 | 4.600 | wipeleft 0.40 s |
| cta (cta) | 14.700 | 18.300 | 3.600 | fade 0.40 s |

## Checagens

| Checagem | OK | Detalhe |
|---|---|---|
| gancho ≤ 3.0 s | ✔ | 2.50 s |
| CTA presente e ≥ 2.5 s | ✔ | 3.60 s |
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
| bitrate de vídeo ≤ 12 Mbps | ✔ | 1.43 Mbps |
| duração 15–20 s | ✔ | 18.300 s |
| duração ≤ 90 s | ✔ | 18.300 s |
| tamanho ≤ 100 MB | ✔ | 3.28 MB |
| moov no início (faststart) | ✔ | True |
| sem faixa de áudio (modo silent) | ✔ | 0 faixa(s) |
| quadro 'inicio' não uniforme | ✔ | desvio-padrão 24.9 |
| quadro 'hook_hook_meio' não uniforme | ✔ | desvio-padrão 58.1 |
| quadro 'scene_s1_meio' não uniforme | ✔ | desvio-padrão 45.7 |
| quadro 'scene_s2_meio' não uniforme | ✔ | desvio-padrão 50.5 |
| quadro 'scene_s3_meio' não uniforme | ✔ | desvio-padrão 45.0 |
| quadro 'cta_cta_meio' não uniforme | ✔ | desvio-padrão 59.0 |
| quadro 'fim' não uniforme | ✔ | desvio-padrão 59.0 |
| logo íntegro (hook) | ✔ | diferença média 8.21 (máx. 14.0) |
| logo íntegro (s1) | ✔ | diferença média 7.75 (máx. 14.0) |
| logo íntegro (s2) | ✔ | diferença média 8.47 (máx. 14.0) |
| logo íntegro (s3) | ✔ | diferença média 8.43 (máx. 14.0) |
| logo íntegro (cta) | ✔ | diferença média 6.72 (máx. 14.0) |
| movimento de câmera presente (s1) | ✔ | diferença média entre quadros 0.794 |
| movimento sem saltos (s1) (aviso) | ✔ | máx/mediana = 1.30 em 11 pares (t=3.65s; limite 3.0) |
| movimento de câmera presente (s2) | ✔ | diferença média entre quadros 0.295 |
| movimento sem saltos (s2) (aviso) | ✔ | máx/mediana = 2.58 em 11 pares (t=8.05s; limite 3.0) |
| movimento de câmera presente (s3) | ✔ | diferença média entre quadros 0.164 |
| movimento sem saltos (s3) (aviso) | ✔ | máx/mediana = 1.24 em 11 pares (t=12.05s; limite 3.0) |

## Origem das imagens

| Cena | Categoria | Arquivo | Tipo | Origem | Licença |
|---|---|---|---|---|---|
| s1 | Tecnologia | `reels/assets/synthetic/s1_tecnologia.jpg` | synthetic_demo | gerado por reel_gen/synth.py (padrão circuit, seed 101) | material próprio do projeto (sintético, sem terceiros) |
| s2 | Casa e cozinha | `reels/assets/synthetic/s2_casa_cozinha.jpg` | synthetic_demo | gerado por reel_gen/synth.py (padrão blobs, seed 202) | material próprio do projeto (sintético, sem terceiros) |
| s3 | Moda e acessórios | `reels/assets/synthetic/s3_moda.jpg` | synthetic_demo | gerado por reel_gen/synth.py (padrão bands, seed 303) | material próprio do projeto (sintético, sem terceiros) |

## Quadros de verificação

- `reels/out/frames/pilot_demo_01/00_inicio.jpg` — inicio (t=0.00s, desvio-padrão 24.9)
- `reels/out/frames/pilot_demo_01/01_hook_hook_meio.jpg` — hook_hook_meio (t=1.05s, desvio-padrão 58.1)
- `reels/out/frames/pilot_demo_01/02_scene_s1_meio.jpg` — scene_s1_meio (t=4.40s, desvio-padrão 45.7)
- `reels/out/frames/pilot_demo_01/03_scene_s2_meio.jpg` — scene_s2_meio (t=8.60s, desvio-padrão 50.5)
- `reels/out/frames/pilot_demo_01/04_scene_s3_meio.jpg` — scene_s3_meio (t=12.80s, desvio-padrão 45.0)
- `reels/out/frames/pilot_demo_01/05_cta_cta_meio.jpg` — cta_cta_meio (t=18.05s, desvio-padrão 59.0)
- `reels/out/frames/pilot_demo_01/06_fim.jpg` — fim (t=18.20s, desvio-padrão 59.0)
