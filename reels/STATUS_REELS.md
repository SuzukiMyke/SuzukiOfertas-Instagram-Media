# STATUS — Gerador de Reels (piloto técnico v1)

Data: 17/11/2026 · Branch: `claude/reel-gerador-v1` (base `claude/gerador-hibrido-v1` @ `967b7c9`)

## Estado

| Item | Estado |
|---|---|
| Gerador (config → camadas → FFmpeg → validação → relatório) | implementado · testado localmente |
| Piloto `pilot_demo_01` (3 categorias, silencioso, sintético) | testado localmente · aprovado nas checagens automáticas |
| Segunda config `example_template` (sem mudar código) | testado localmente · aprovado nas checagens automáticas |
| CTA independente (`render_cta_only`) | testado localmente |
| Arquitetura de áudio licenciado / `VoiceProvider` | implementado (só montagem de comando, com testes unitários) · **não usado** |
| Validação com serviço real (upload no Instagram, celular) | **pendente** (decisão do usuário) |
| Aprovação para produção | **não aprovado** — piloto é demonstração técnica |

Nada publicado, agendado ou enviado a serviços. Nenhum serviço pago. Nenhuma imagem de IA gerada. `main` intacta.

## Pré-verificações

- Base `claude/gerador-hibrido-v1` = `967b7c9f8a99d0dab792f69e5454418384b40fd0` (conferido com `git ls-remote`).
- `main` = `f1674b30e1976ac266730435a340c12677ff0761` (antes e depois).
- Logo oficial e `brand/identidade-visual.md` já estavam na base (1254×1254) — nada importado de `claude/identidade-visual`.
- Ferramentas: Python 3.13.18 · Pillow 12.3.0 · FFmpeg/FFprobe 6.1.1-3ubuntu5 · `libx264` e `aac` presentes · filtros `zoompan`, `xfade`, `overlay`, `scale`, `crop`, `fade`, `afade`, `amix`, `loudnorm` presentes. Sem pytest/numpy (testes com `unittest`).
- Fontes: Inter / Inter Display do sistema (`fonts-inter`, licença SIL OFL 1.1 / Apache-2.0, conforme `/usr/share/doc/fonts-inter/copyright`). Nenhuma fonte baixada.

### Fotos do projeto avaliadas (nenhuma usada no piloto)

| ID | Origem | Status | Motivo de não usar |
|---|---|---|---|
| `flux-0001` (`photos/foto_flux_01.jpg`, base) | IA (FLUX) | aprovação **pendente** | não aprovada; "não usar como foto de produto real" |
| `nb-0001` (branch `claude/teste-nanobanana-01`) | IA (Nano Banana) | aprovada **só para ambientação** | restrição "não destacar nem ampliar" (o reel aplica zoom) e eletrodomésticos com logotipos ilegíveis de terceiros |

Sem foto de produto real utilizável → três cenas sintéticas (`synth.py`, degradês e formas neutras), todas rotuladas "DEMONSTRAÇÃO TÉCNICA — NÃO É PRODUTO À VENDA". Nenhum arquivo importado de outras branches.

## Resultados (rodada final)

| Reel | Duração | Tamanho | Bitrate vídeo | Render | Pico memória | SHA-256 |
|---|---|---|---|---|---|---|
| `pilot_demo_01` | 18,300 s (549 quadros) | 3,28 MB | 1,43 Mbps | 34.54 s | 491.3 MB | `1aadb48a3f06095cc9a84c98c592a7c129f628dac2245d6ae3533f4d48e2a1df` (quadros: `93c5c15ca189b3a3b86bbc14449ec7a4`) |
| `example_template` | 18,133 s | 4,01 MB | 1,76 Mbps | 35.86 s | 490.8 MB | `26147ec1945f9799…` |
| `pilot_demo_01_cta` | 3,600 s | — | — | ~6 s | ~410 MB | (renderizado nos testes) |

- MP4 do piloto: 1080×1920, 30/1 fps constante, H.264 High, yuv420p, SAR 1:1, `moov` antes de `mdat`, sem faixa de áudio.
- Determinismo: os **quadros decodificados** são idênticos entre execuções (hash `framemd5`, verificado no teste e2e). Com `-threads 2` o x264 ocasionalmente varia alguns bytes do fluxo H.264 (medido: 3 de 10 execuções do mesmo comando; ~174 bytes diferentes, mesma imagem decodificada). Com `output.threads = 1` o MP4 é idêntico byte a byte (10/10; coberto por teste). Mantido `-threads 2` conforme o GOAL.
- Testes: **70/70 OK** (`python3 -m unittest discover -s tests -t .`, ~142 s): config, regras, linha do tempo/movimento, camadas, comando FFmpeg, áudio (montagem), validador e e2e (piloto, segunda config, CTA isolado, determinismo).
- Relatórios: `reels/out/pilot_demo_01_report.{json,md}` e `reels/out/example_template_report.{json,md}`.

## Decisões técnicas

1. **Câmera**: `zoompan` sobre fundo pré-ampliado 2× (2160×3840) em **RGB24**. O zoompan arredonda a janela para pixels inteiros da entrada; com 2× o erro cai para 0,5 px na saída e, em RGB, x/y não são forçados a valores pares (como em yuv420p). Medido no fundo isolado: razão máx/mediana das diferenças entre quadros 1,45 (2×) vs 1,23 (3×, +25% de tempo). Mantido 2× (configurável em `output.supersample`).
2. **Render em dois passes** (um comando por segmento + passe final com `xfade`). Em passe único, com 36 entradas, o pico foi ~1,1 GB; em dois passes, com decodificadores de 1 thread no passe final, ~0,5 GB. Intermediários H.264 CRF 12 (`output.intermediate_crf`).
3. **Texto** sempre em PNG (Pillow) sobreposto com `overlay` + `fade` no alfa + deslize com *ease-out*; sem `drawtext`. Quebra de linha pela largura real da fonte, equilibrada (sem palavra órfã; travessão nunca abre linha).
4. **Margem segura assimétrica**: elementos centralizados no centro da área segura (x = 512), não do quadro.
5. **Contraste**: calculado no pior caso (pixel mais claro e mais escuro do fundo sob o painel). A etiqueta vermelha com texto branco (4,25:1) foi reprovada pelo próprio validador; o estilo `tag` passou a azul-escuro com texto amarelo.
6. **Caminhos** nas configs são relativos à raiz do repositório (o exemplo do GOAL usava `assets/...`; adaptado para `reels/assets/...`).
7. **Pico de movimento em s2** (razão ~2,6, limite 3,0 — aviso, não bloqueante): coincide com o quadro-chave do x264 (quadro 250 ≈ 8,33 s), não com o movimento da câmera.
8. Saída sem metadados de data/encoder (`-map_metadata -1`, `bitexact`).

## Limitações e pendências

- Sem música, narração ou efeitos (arquitetura pronta; exige faixa com licença comercial documentada).
- Sem fotos reais de produtos; cenas sintéticas apenas demonstram o motor.
- Primeiro quadro (t=0) mostra o fundo antes do texto do gancho entrar (0,15 s); a capa do Reel deve ser escolhida no upload.
- Margens seguras são valores iniciais; conferir no app do Instagram em celular real.
- Paleta é aproximada (não oficial). Logo aplicado com cantos arredondados e opacidade 0,95 (cores intactas).
- Medição de memória = maior RSS entre os processos-filho (FFmpeg); sem medir o próprio Python.
- Validação visual feita por inspeção de quadros extraídos; falta revisão humana no celular.
