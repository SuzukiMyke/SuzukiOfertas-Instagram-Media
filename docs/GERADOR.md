# Gerador híbrido de carrosséis — Suzuki Ofertas

Gera slides de Instagram em 1080 × 1350 a partir de fotos com duas origens:

| Provedor | ID | Como entra | Custo |
|---|---|---|---|
| Cloudflare Workers AI, FLUX.1 schnell (`cloudflare-flux`) | `flux-0001`… | `python3 -m gerador flux "…" --confirmar` | cota gratuita diária (limite de proteção 9000 neurônios/dia; ≈173 por foto) |
| Gemini Nano Banana (`nano-banana`) | `nb-0001`… | imagem criada e aprovada por você, importada com `importar` | nenhum (sem chamada de API) |
| Foto real (`foto-real`) | `real-0001`… | `importar --provedor foto-real` | nenhum |

Textos, fontes, cores e logotipo são aplicados **pelo código (Pillow)**, nunca pela IA.
Requisitos: Python 3.12+ e Pillow (já instalados no ambiente). Nada mais.

## Estrutura

```
gerador/
  catalogo.py    catálogo de fotos (photos/catalogo.json): IDs, hash, aprovação
  importar.py    importação de JPG/PNG/WebP externos (Nano Banana, foto real)
  flux.py        geração FLUX com confirmação explícita e proteção de cota
  selecao.py     escolhe a foto de cada slide (ID fixo ou "auto"), sem repetição
  identidade.py  cores, fontes, logotipo como marca-d'água (original intocado)
  layouts.py     foto_topo · foto_cheia · cartao
  render.py      primitivas Pillow (recorte sem deformar, degradês, texto)
  validacao.py   checa formato, tamanho, foto visível, margens, logo
  carrossel.py   config → seleção → render → exportação + manifest.json
  __main__.py    linha de comando
photos/
  catalogo.json           índice de todas as fotos
  <id>.jpg                versão interna usada nos slides
  originais/<id>__nome.*  arquivo original, byte a byte
exemplos/carrossel_exemplo.json
tests/test_gerador.py
carrosseis/<id>/slide_01.jpg … + manifest.json   (saída)
```

### Registro de cada foto em `photos/catalogo.json`

```json
"nb-0001": {
  "id": "nb-0001",
  "provedor": "nano-banana",
  "nome_arquivo_original": "Gemini_Generated_Image_x1y2.png",
  "sha256_original": "…", "sha256": "…",
  "largura": 1536, "altura": 2048, "formato_original": "PNG",
  "data": "2026-11-17T12:00:00Z", "tipo_data": "importacao",
  "origem": "ia",
  "descricao": "Pessoa organizando compras na cozinha",
  "prompt": "…", 
  "restricoes_uso": ["Imagem gerada por IA: não representar como fotografia real", "…"],
  "caminho_github": "photos/nb-0001.jpg",
  "caminho_original": "photos/originais/nb-0001__Gemini_Generated_Image_x1y2.png",
  "aprovacao": {"status": "aprovada", "por": "Myke", "data": "…", "nota": "ok no celular"},
  "repositorio": "SuzukiMyke/SuzukiOfertas-Instagram-Media"
}
```

`aprovacao.status` é `pendente`, `aprovada` ou `rejeitada`. Toda foto nova entra
como **pendente**; aprovar exige o nome de quem aprovou.

## Importar uma foto do Nano Banana

1. Crie e escolha a imagem no Gemini; envie o arquivo para a sessão (ou faça commit dele numa pasta temporária).
2. Importe registrando a aprovação:

```bash
python3 -m gerador importar /caminho/Gemini_Generated_Image.png --descricao "Cozinha com sacolas de compras" --prompt "texto usado no Gemini" --aprovado-por "Myke"
```

Sem `--aprovado-por` a foto fica pendente; aprove depois com:

```bash
python3 -m gerador aprovar nb-0001 --por "Myke" --nota "aprovada no celular"
```

O comando valida o formato real do arquivo, a integridade e o tamanho mínimo
(768 px no menor lado), corrige a rotação EXIF, guarda o original e cria
`photos/nb-0001.jpg` (JPEG qualidade 95, mesmas dimensões). Se o mesmo arquivo
já foi importado (mesmo SHA-256), apenas informa o ID existente.

Ver o catálogo:

```bash
python3 -m gerador listar
```

## Montar um carrossel

Crie um JSON como `exemplos/carrossel_exemplo.json`:

```json
{
  "id": "5-erros-compras",
  "slides": [
    {"layout": "foto_topo", "foto": "flux-0001", "titulo": "5 ERROS QUE FAZEM",
     "destaque": "VOCÊ GASTAR MAIS!", "texto": "Descubra como evitar desperdícios."},
    {"layout": "cartao", "foto": "nb-0001", "foco": [0.5, 0.3],
     "titulo": "ERRO 1:", "destaque": "COMPRAR POR IMPULSO"},
    {"layout": "foto_cheia", "foto": "auto", "provedor": "nano-banana",
     "titulo": "ERRO 2:", "destaque": "IGNORAR O FRETE"}
  ]
}
```

Campos de cada slide: `layout`, `foto` (ID ou `"auto"`), `titulo` (branco),
`destaque` (amarelo), `texto` (complementar), `foco` ([x, y] de 0 a 1 para o
recorte), `reutilizar` (permite repetir uma foto já usada), `provedor` (filtro do `"auto"`).

Regras de seleção:
- `"auto"` pega a próxima foto **aprovada** ainda não usada no carrossel.
- A mesma foto só se repete com `"reutilizar": true`.
- Fotos pendentes só entram com `"permitir_fotos_pendentes": true` no topo do JSON (o resultado fica marcado `rascunho`).
- Foto rejeitada ou arquivo ausente interrompe a geração. Nunca há troca por fundo liso.

Gerar:

```bash
python3 -m gerador carrossel exemplos/carrossel_exemplo.json
```

Saída em `carrosseis/<id>/`, com `manifest.json` (foto de cada slide, SHA-256,
resultado da validação). Código de saída 3 = algum slide reprovado na validação.

## Gerar uma foto FLUX (opcional, consome cota)

```bash
python3 -m gerador flux "Photorealistic photo of a tidy pantry with groceries, warm daylight" --descricao "Despensa organizada" --confirmar
```

Gera **uma** foto por chamada. Sem `--confirmar` não gera nada. O comando recusa a
geração se o consumo do dia registrado no catálogo, somado à estimativa, passar
de `FLUX_LIMITE_NEURONIOS_DIA` (padrão 9000). A autenticação vem do Network Secret
da sessão: nenhum token fica no código. A foto entra como pendente.

Variáveis (sem credenciais): `CLOUDFLARE_ACCOUNT_ID`, `FLUX_LIMITE_NEURONIOS_DIA`, `FLUX_MAX_IMAGENS`.

## Testes

```bash
python3.12 -m unittest discover -s tests -v
```

Sem rede e sem IA: usam imagens sintéticas em pasta temporária e uma API FLUX simulada.

## Uso futuro em tarefas agendadas

Fluxo previsto para uma execução automática na nuvem (ainda **não** configurado):

1. A tarefa recebe/escreve o JSON do carrossel do dia (textos + IDs de fotos aprovadas ou `"auto"`).
2. Se faltar foto aprovada, pode gerar no máximo uma foto FLUX com `--confirmar`; ela fica **pendente** e o carrossel sai como rascunho, aguardando sua aprovação.
3. Roda `python3 -m gerador carrossel …`; se o código de saída não for 0, para e relata.
4. Faz commit de `carrosseis/<id>/` e do catálogo numa branch própria.
5. Publicação/agendamento (Metricool) fica para uma etapa posterior, com aprovação humana.

O script legado `scripts/gerar_slide.py` (etapa 4.8) continua funcionando e não é usado pelo gerador.
