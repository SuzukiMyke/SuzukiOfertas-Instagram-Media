# Esquema JSON do reel (`schema_version: 1`)

Validação em `reel_gen/config.py` (biblioteca padrão). **Chave desconhecida = erro.**
Chaves que começam com `_` são comentários e são ignoradas. Campos omitidos herdam de
`configs/defaults.json`. Caminhos relativos são resolvidos a partir da **raiz do repositório**
(ex.: `reels/assets/synthetic/s1_tecnologia.jpg`, `brand/logo-suzuki-ofertas.png`).

| Campo | Tipo | Obrig. | Observações |
|---|---|---|---|
| `schema_version` | int | sim | sempre `1` |
| `id` | texto | sim | `[a-z0-9_-]`, nomeia relatório e quadros |
| `output` | objeto | sim* | `width`, `height`, `fps`, `crf` (0–51), `intermediate_crf`, `preset` (ultrafast…medium), `threads` (1–8), `max_bitrate_mbps` (teto VBV), `supersample` (1–3, ampliação do fundo para o zoom), `filename` (`*.mp4`) |
| `theme.palette` | objeto | sim* | `bg`, `primary`, `accent`, `alert`, `text`, `text_dark` em `#RRGGBB` (paleta aproximada; configurável) |
| `theme.font` | objeto | sim* | `bold`, `regular`, `label`: caminho de arquivo ou `auto:titulo` / `auto:texto` / `auto:rotulo` |
| `theme.sizes` | objeto | sim* | px: `hook`, `title`, `subtitle`, `highlight`, `category`, `label`, `cta_headline`, `button`, `button_sub`, `disclosure` |
| `theme.panel` | objeto | sim* | `color` (nome da paleta), `opacity`, `radius`, `padding` `[x, y]` |
| `safe_zone` | objeto | sim* | `top`, `bottom`, `left`, `right` (px). Nenhum texto/logo pode sair dela (inclusive durante o deslize) |
| `demo_label` | objeto | sim* | `enabled`, `text`. Obrigatório `enabled: true` com material `synthetic_demo` |
| `illustrative_label` | texto | sim* | rótulo das imagens `illustrative` (padrão "Imagem ilustrativa") |
| `animation` | objeto | sim* | `fade_in`, `fade_out`, `slide_px`, `stagger`, `text_delay` (s/px) e `hook_dim` (0–0,9) |
| `hook` | objeto | não | `duration` (≤ `validation.hook_max`), `lines` (1–2), `background` (`scene:N` ou `brand`), `animation` (`slide_up`, `slide_left`, `fade`, `none`), `camera` (opcional), `transition_out` |
| `scenes[]` | lista 1–10 | sim | ver abaixo |
| `cta` | objeto | não | `duration` (≥ `cta_min`), `headline`, `buttons` (chaves ou rótulos de `channels`), `links_display` (`channels_official`), `show_logo`, `disclosure` (obrigatório, não vazio), `independent_background`, `camera` |
| `channels` | mapa | se houver CTA | `{chave: {label, url, display}}`. Chave e URL devem constar em `configs/content_policy.json` → `official_channels` |
| `logo` | objeto | sim | `path`, `position` (`top_left`/`top_right`), `size_px`, `cta_size_px`, `opacity` (só multiplica o alfa), `show_on_scenes`, `mask` (`rounded`/`ellipse`/`none`) |
| `audio` | objeto | sim* | `mode` (`silent`/`licensed`), `tracks`, `silent_track`, `loudnorm` `{I, TP, LRA}`, `ducking` |
| `policy.extra_forbidden_terms` | lista | não | soma-se aos termos proibidos da política |
| `validation` | objeto | sim* | limites da validação: duração, bitrate, tamanho, gancho/CTA, fontes mínimas (`min_body_px` 44, `min_title_px` 72), contraste (`min_contrast` 4,5), `min_frame_stddev`, `motion_spike_ratio`, `logo_max_mad` |

\* tem padrão em `defaults.json`.

## Cena (`scenes[]`)

| Campo | Obrig. | Observações |
|---|---|---|
| `id`, `category`, `title` | sim | textos não vazios |
| `duration` | sim | segundos (arredondados para quadros) |
| `source` | sim | `path` (arquivo local; URL remota é erro), `kind` (`real_photo`, `illustrative`, `synthetic_demo`), `origin`, `license` (obrigatórios), `catalog_id`, `focus` `[x, y]` |
| `subtitle` | não | |
| `highlights[]` | não | até 3: `text`, `at` (s, relativo à cena), `style` (`pill`/`tag`) |
| `camera` | sim | `zoom_start`/`zoom_end` (1–3), `pan_start`/`pan_end` (centro da janela, 0–1), `easing` (`linear`, `ease_in`, `ease_out`, `ease_in_out`) |
| `text_animation` | não | `slide_up` (padrão), `slide_left`, `fade`, `none` |
| `transition_out` | não | `type` (fade, dissolve, slideleft/right/up/down, wipeleft/right/up/down, circleopen/close, smoothleft/up), `duration` (0,1–1,5 s; padrão fade 0,4) |
| `label`, `badge` | não | rótulo próprio da cena; selo de texto |
| `product_model` | não | **proibido** se `kind` ≠ `real_photo` |
| `price`, `discount`, `stock`, `rating` | não | só com `verified_at` + `source_url` (https) **e** `kind = real_photo` |

## Áudio licenciado (`audio.mode = "licensed"`, preparado, não usado no piloto)

Cada faixa: `file` (dentro de `reels/assets/audio_licensed/`), `type` (`music`/`voice`/`sfx`),
`license_id`, `license_url_or_proof`, `author`, `start`, `gain_db`, `loop`, `fade_in`, `fade_out`.
Mixagem: `volume` + `afade` + `adelay` → `amix` → `loudnorm`; com `ducking: true` a música
é comprimida sob a voz (`sidechaincompress`). Narração/TTS: só a interface `VoiceProvider`.
