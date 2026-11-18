# orquestrador_b2

Fluxo ponta a ponta FICTÍCIO: ficha de curadoria → receptor 1.1 → ponte → carrossel (3 a 5 slides) → folha de contato e relatórios. Sem rede, sem publicação.

```bash
python3 -m orquestrador_b2 FICHA.json --saida DIR_FORA_DO_REPO [--agora ISO] [--estilo auto|v1|v2] [--aprovar-fundo-ficticio]
```

## Estilo editorial v2 (B2R)

`--estilo auto|v1|v2` (padrão `auto`: **v1** para a fixture fictícia legada da B2 — reproduz exatamente a saída anterior — e **v2** para as demais).
O v2 usa os layouts `ilustracao_capa`, `destaque_numerico`, `lista_caracteristicas` e `cta_seguir`, ilustração gráfica por categoria
(`ilustracoes.py`, provedor `composicao-grafica`, registrada como pendente) e fundos sem logotipo embutido. Títulos e números são extraídos dos
fatos liberados pela ponte; texto reprovado pela política de títulos/alegações é descartado e, com menos de 3 slides, o carrossel é bloqueado.
Lista: título derivado dos fatos (ex.: `CONEXÃO E ESTOJO`), neutro se faltar informação. CTA: "CURTIU ESSE ACHADO? SIGA O PERFIL!", com menção secundária ao WhatsApp e ao Telegram, sem links quando não fornecidos e sem citar legenda ou bio.

`--aprovar-fundo-ficticio` só vale para fixtures reconhecidas por **conteúdo** (hash) — a legada e as três de `exemplos_ficticios/` — e apenas em
catálogo temporário; é aprovação de teste, sem valor de homologação humana.

Entrega visual (fora do repositório; imagens nunca são versionadas):

```bash
python3 -m orquestrador_b2.entrega --saida /caminho/fora/do/repo --agora 2026-11-18T12:00:00Z
```

Gera, por carrossel, JPEG + PNG + `folha_de_contato.png` + `relatorio_visual.md` + `relatorio_b2.json`, além de `folha_geral.png` e
`relatorio_consolidado.{md,json}`. As medições são automáticas; a aprovação visual definitiva é humana.
